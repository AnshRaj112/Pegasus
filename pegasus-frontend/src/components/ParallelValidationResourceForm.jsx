/**
 * Resource review UI: max parallel jobs + auto-tune only.
 * Threads/disk policy stays on server defaults (env / queue defaults).
 */

export function buildResourceProjection(queueInfo, concurrencySlider, autoTuneEnabled) {
  const ra = queueInfo?.resource_advisor ?? null
  const cpuCores = queueInfo?.cpu_cores_available ?? ra?.system?.cpu_cores ?? null
  const perJobRam = ra?.per_job_estimate?.ram_bytes ?? 0
  const perJobDisk = ra?.per_job_estimate?.disk_bytes ?? 0
  const availRam = ra?.system?.available_ram_bytes ?? 0
  const availDisk = ra?.system?.available_disk_bytes ?? 0

  let jobs = Math.max(1, Math.floor(concurrencySlider) || 1)
  const effectiveMax = queueInfo?.effective_max_concurrency
  if (autoTuneEnabled && effectiveMax != null) {
    jobs = Math.min(jobs, Math.max(1, effectiveMax))
  }

  return {
    jobs,
    recommended: ra?.recommended_max_concurrency ?? null,
    cpuCores,
    ramFreeGib: ra?.system?.available_ram_gib,
    diskFreeGib: ra?.system?.available_disk_gib,
    perJobRamMib: ra?.per_job_estimate?.ram_mib,
    ramShareOfAvailable: availRam > 0 ? (jobs * perJobRam) / availRam : null,
    diskShareOfAvailable: availDisk > 0 ? (jobs * perJobDisk) / availDisk : null,
  }
}

export default function ParallelValidationResourceForm({
  queueInfo,
  queueLoading = false,
  queueError = '',
  concurrencySlider,
  onConcurrencyChange,
  autoTuneEnabled,
  onAutoTuneChange,
  onRefresh,
  disabled = false,
  theme = 'light',
  showQueueStatus = true,
}) {
  const ra = queueInfo?.resource_advisor ?? null
  const cpuCores = queueInfo?.cpu_cores_available ?? ra?.system?.cpu_cores ?? null
  const effectiveMax = queueInfo?.effective_max_concurrency ?? null
  const projection = buildResourceProjection(queueInfo, concurrencySlider, autoTuneEnabled)
  const recommended = projection.recommended

  const practicalSliderMax = Math.min(
    32,
    ra?.limits?.max_safe_by_cpu ?? cpuCores ?? 32,
    recommended != null ? Math.max(recommended, cpuCores ?? 1) : cpuCores ?? 8,
  )
  const sliderMax = Math.max(
    1,
    concurrencySlider,
    queueInfo?.max_concurrency ?? 1,
    cpuCores ?? 1,
    recommended ?? 1,
    practicalSliderMax,
  )

  const hintCls = theme === 'dark' ? 'text-xs leading-relaxed text-slate-400' : 'text-xs leading-relaxed text-slate-500'
  const sectionTitle = theme === 'dark' ? 'text-sm font-semibold text-slate-200' : 'text-sm font-semibold text-slate-800'

  return (
    <div className="space-y-5">
      {queueLoading ? (
        <p className={theme === 'dark' ? 'text-sm text-slate-400' : 'text-sm text-slate-500'}>Loading server resources…</p>
      ) : null}

      {queueError ? (
        <div
          className={
            theme === 'dark'
              ? 'rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-300'
              : 'rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800'
          }
        >
          {queueError}
          {onRefresh ? (
            <button type="button" onClick={onRefresh} className="ml-2 underline decoration-dotted hover:no-underline">
              Retry
            </button>
          ) : null}
        </div>
      ) : null}

      {!queueLoading && ra ? (
        <>
          {showQueueStatus && queueInfo ? (
            <div
              className={
                theme === 'dark'
                  ? 'flex flex-wrap gap-3 rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-xs text-slate-300'
                  : 'flex flex-wrap gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600'
              }
            >
              <span>
                <strong className={theme === 'dark' ? 'text-slate-100' : 'text-slate-800'}>Queue:</strong>{' '}
                {queueInfo.pending ?? 0} pending · {queueInfo.running ?? 0} running
              </span>
              {effectiveMax != null && autoTuneEnabled && effectiveMax < concurrencySlider ? (
                <span>
                  <strong className={theme === 'dark' ? 'text-slate-100' : 'text-slate-800'}>Effective cap:</strong>{' '}
                  {effectiveMax} (auto-tune)
                </span>
              ) : null}
            </div>
          ) : null}

          <p className={hintCls}>
            {cpuCores ?? '?'} CPU cores · {projection.ramFreeGib ?? '?'} GiB RAM free ·{' '}
            {projection.diskFreeGib ?? '?'} GiB disk free.
            {recommended != null ? (
              <>
                {' '}
                Server recommends <strong>{recommended}</strong> parallel job{recommended === 1 ? '' : 's'}.
              </>
            ) : null}
          </p>

          <div>
            <h3 className={sectionTitle}>Max parallel jobs</h3>
            <p className={`mt-1 ${hintCls}`}>
              How many validations may run at the same time. Each job uses its own worker process.
            </p>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <label
                className={theme === 'dark' ? 'text-sm font-semibold text-slate-200' : 'text-sm font-semibold text-slate-700'}
                htmlFor="pegasus-parallel-jobs-range"
              >
                Parallel jobs
              </label>
              <div className="flex items-center gap-2">
                {recommended != null && concurrencySlider !== recommended ? (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onConcurrencyChange(recommended)}
                    className={
                      theme === 'dark'
                        ? 'rounded bg-white/10 px-2 py-1 text-xs font-semibold text-slate-200 hover:bg-white/15'
                        : 'rounded bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 hover:bg-blue-200'
                    }
                  >
                    Use recommended ({recommended})
                  </button>
                ) : null}
                <input
                  type="number"
                  min={1}
                  value={concurrencySlider}
                  disabled={disabled}
                  onChange={(ev) => {
                    const n = Number(ev.target.value)
                    if (Number.isFinite(n) && n >= 1) onConcurrencyChange(Math.floor(n))
                  }}
                  className={
                    theme === 'dark'
                      ? 'w-20 rounded-md border border-white/20 bg-white/5 px-2 py-1 text-center font-mono text-sm font-bold text-slate-100'
                      : 'w-20 rounded-md border border-[#F1F1F1] bg-white px-2 py-1 text-center font-mono text-sm font-bold text-[#EB4C4C]'
                  }
                  aria-label="Max parallel jobs"
                />
              </div>
            </div>

            <input
              id="pegasus-parallel-jobs-range"
              type="range"
              min={1}
              max={sliderMax}
              step={1}
              value={Math.min(concurrencySlider, sliderMax)}
              disabled={disabled}
              onChange={(ev) => onConcurrencyChange(Number(ev.target.value))}
              className="mt-2 w-full cursor-pointer accent-[#EB4C4C] disabled:cursor-not-allowed disabled:opacity-50"
            />
            <div className="mt-1 flex justify-between text-xs text-slate-400">
              <span>1 (one at a time)</span>
              <span>up to {sliderMax}</span>
            </div>
          </div>

          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-[#F1F1F1] p-4 dark:border-white/10">
            <input
              type="checkbox"
              checked={autoTuneEnabled}
              disabled={disabled}
              onChange={(ev) => onAutoTuneChange(ev.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-[#EB4C4C] accent-[#EB4C4C]"
            />
            <div>
              <span className={theme === 'dark' ? 'text-sm font-semibold text-slate-200' : 'text-sm font-semibold text-slate-700'}>
                Auto-tune
              </span>
              <p className={`mt-1 ${hintCls}`}>
                When on, the server may run fewer jobs than you set if RAM, disk, or swap are tight. When off, only your
                parallel job count is used.
              </p>
            </div>
          </label>

          {ra.warnings?.length ? (
            <div className="space-y-2">
              {ra.warnings.map((w, i) => (
                <div
                  key={i}
                  className={
                    theme === 'dark'
                      ? 'rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200'
                      : 'rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800'
                  }
                >
                  {w}
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  )
}