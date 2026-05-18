/**
 * Detailed resource review UI for parallel validation (queue settings).
 * Used by ValidationPanel and ParallelValidationModal.
 */

function formatGiB(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '—'
  return `${(bytes / 1024 ** 3).toFixed(2)} GiB`
}

function formatMiB(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '—'
  return `${Math.round(bytes / 1024 ** 2)} MiB`
}

function formatPct(fraction) {
  if (fraction == null || !Number.isFinite(fraction)) return null
  return `${Math.max(0, Math.min(100, fraction * 100)).toFixed(0)}%`
}

function swapLabel(pressure) {
  if (pressure == null || !Number.isFinite(pressure)) return 'Unknown'
  const pct = pressure * 100
  if (pct < 5) return 'Low'
  if (pct < 15) return 'Moderate'
  return 'High'
}

export function buildResourceProjection(
  queueInfo,
  concurrencySlider,
  autoTuneEnabled,
  threadsPerJob = 0,
) {
  const ra = queueInfo?.resource_advisor ?? null
  const cpuCores = queueInfo?.cpu_cores_available ?? ra?.system?.cpu_cores ?? null
  const effectiveThreads =
    queueInfo?.effective_threads_per_job ??
    (threadsPerJob > 0 ? threadsPerJob : cpuCores) ??
    null
  const perJobRam = ra?.per_job_estimate?.ram_bytes ?? 0
  const perJobDisk = ra?.per_job_estimate?.disk_bytes ?? 0
  const availRam = ra?.system?.available_ram_bytes ?? 0
  const availDisk = ra?.system?.available_disk_bytes ?? 0
  const totalRam = ra?.system?.total_ram_bytes ?? 0
  const totalDisk = ra?.system?.total_disk_bytes ?? 0
  const runningRam = ra?.running_jobs_estimated_ram_bytes ?? 0
  const runningCount = queueInfo?.running ?? 0

  let jobs = Math.max(1, Math.floor(concurrencySlider) || 1)
  const effectiveMax = queueInfo?.effective_max_concurrency
  if (autoTuneEnabled && effectiveMax != null) {
    jobs = Math.min(jobs, Math.max(1, effectiveMax))
  }

  const projectedNewRam = jobs * perJobRam
  const projectedDisk = jobs * perJobDisk
  const totalProjectedRam = runningRam + projectedNewRam
  const threadsEach = effectiveThreads ?? (threadsPerJob > 0 ? threadsPerJob : cpuCores)
  const coresPerJobApprox =
    threadsEach != null
      ? threadsEach
      : cpuCores != null && jobs > 0
        ? Math.round((cpuCores / jobs) * 10) / 10
        : null
  const totalThreadDemand =
    threadsEach != null && jobs > 0 ? threadsEach * jobs : null

  const ramShareOfAvailable = availRam > 0 ? projectedNewRam / availRam : null
  const diskShareOfAvailable = availDisk > 0 ? projectedDisk / availDisk : null
  const ramUsedSystemPct = totalRam > 0 ? 1 - availRam / totalRam : null
  const diskUsedSystemPct = totalDisk > 0 ? 1 - availDisk / totalDisk : null

  return {
    jobs,
    perJobRam,
    perJobDisk,
    projectedNewRam,
    projectedDisk,
    totalProjectedRam,
    runningRam,
    runningCount,
    coresPerJobApprox,
    cpuCores,
    ramShareOfAvailable,
    diskShareOfAvailable,
    ramUsedSystemPct,
    diskUsedSystemPct,
    limits: ra?.limits ?? {},
    recommended: ra?.recommended_max_concurrency ?? null,
    effectiveThreads,
    totalThreadDemand,
    threadsPerJob,
  }
}

function ResourceSlider({
  id,
  label,
  hint,
  min,
  max,
  step,
  value,
  displayValue,
  disabled,
  theme,
  onChange,
  leftLabel,
  rightLabel,
}) {
  const labelCls = theme === 'dark' ? 'text-sm font-semibold text-slate-200' : 'text-sm font-semibold text-slate-700'
  return (
    <div className="mt-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className={labelCls} htmlFor={id}>
          {label}
        </label>
        <span className="font-mono text-sm font-bold text-[#EB4C4C]">{displayValue}</span>
      </div>
      {hint ? <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hint}</p> : null}
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(ev) => onChange(Number(ev.target.value))}
        className="mt-2 w-full cursor-pointer accent-[#EB4C4C] disabled:cursor-not-allowed disabled:opacity-50"
      />
      <div className="mt-1 flex justify-between text-xs text-slate-400">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
    </div>
  )
}

function UsageBar({ fraction, theme }) {
  if (fraction == null || !Number.isFinite(fraction)) return null
  const pct = Math.min(100, Math.max(0, fraction * 100))
  const barColor =
    pct >= 90 ? 'bg-rose-500' : pct >= 75 ? 'bg-amber-500' : pct >= 50 ? 'bg-[#EB4C4C]' : 'bg-emerald-500'
  const track = theme === 'dark' ? 'bg-white/10' : 'bg-slate-200'
  return (
    <div className={`mt-2 h-2 w-full overflow-hidden rounded-full ${track}`} role="presentation">
      <div className={`h-full rounded-full transition-all duration-300 ${barColor}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

function MetricCard({ label, value, sub, children, theme }) {
  const card =
    theme === 'dark'
      ? 'rounded-xl border border-white/10 bg-white/5 p-4'
      : 'rounded-xl border border-[#F1F1F1] bg-[#FAFAFA] p-4'
  const labelCls = theme === 'dark' ? 'text-[11px] font-semibold uppercase tracking-widest text-slate-400' : 'text-xs font-semibold uppercase tracking-widest text-slate-400'
  const valueCls = theme === 'dark' ? 'mt-1 font-mono text-lg font-bold text-slate-100' : 'mt-1 font-mono text-lg font-bold text-slate-800'
  const subCls = theme === 'dark' ? 'mt-1 text-xs text-slate-400' : 'mt-1 text-xs text-slate-500'
  return (
    <div className={card}>
      <span className={labelCls}>{label}</span>
      <div className={valueCls}>{value}</div>
      {sub ? <p className={subCls}>{sub}</p> : null}
      {children}
    </div>
  )
}

export default function ParallelValidationResourceForm({
  queueInfo,
  queueLoading = false,
  queueError = '',
  concurrencySlider,
  onConcurrencyChange,
  threadsPerJob,
  onThreadsPerJobChange,
  diskHeadroomMultiplier,
  onDiskHeadroomMultiplierChange,
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
  const projection = buildResourceProjection(
    queueInfo,
    concurrencySlider,
    autoTuneEnabled,
    threadsPerJob,
  )

  const recommended = ra?.recommended_max_concurrency ?? null
  // Slider caps parallel *jobs*, not RAM slots (max_safe_by_ram can be hundreds — misleading on the UI).
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

  const swapPressure = ra?.system?.swap_pressure
  const hintCls = theme === 'dark' ? 'text-xs leading-relaxed text-slate-400' : 'text-xs leading-relaxed text-slate-500'
  const sectionTitle = theme === 'dark' ? 'text-sm font-semibold text-slate-200' : 'text-sm font-semibold text-slate-800'
  const tableWrap = theme === 'dark' ? 'overflow-hidden rounded-xl border border-white/10' : 'overflow-hidden rounded-xl border border-[#F1F1F1]'
  const thCls = theme === 'dark' ? 'bg-white/5 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-400' : 'bg-slate-50 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500'
  const tdCls = theme === 'dark' ? 'border-t border-white/10 px-3 py-2.5 text-xs text-slate-300' : 'border-t border-[#F1F1F1] px-3 py-2.5 text-xs text-slate-700'
  const tdMono = `${tdCls} font-mono font-semibold`

  return (
    <div className="space-y-6">
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
            <button
              type="button"
              onClick={onRefresh}
              className="ml-2 underline decoration-dotted hover:no-underline"
            >
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
                  ? 'flex flex-wrap gap-3 rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-xs'
                  : 'flex flex-wrap gap-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600'
              }
            >
              <span>
                <strong className={theme === 'dark' ? 'text-slate-200' : 'text-slate-800'}>Queue:</strong>{' '}
                {queueInfo.pending ?? 0} pending · {queueInfo.running ?? 0} running
              </span>
              <span>
                <strong className={theme === 'dark' ? 'text-slate-200' : 'text-slate-800'}>Your cap:</strong>{' '}
                {concurrencySlider} job{concurrencySlider === 1 ? '' : 's'}
              </span>
              {effectiveMax != null ? (
                <span>
                  <strong className={theme === 'dark' ? 'text-slate-200' : 'text-slate-800'}>Effective now:</strong>{' '}
                  {effectiveMax}
                  {autoTuneEnabled && effectiveMax < concurrencySlider ? ' (auto-tune)' : ''}
                </span>
              ) : null}
            </div>
          ) : null}

          <div>
            <h3 className={sectionTitle}>Server snapshot</h3>
            <p className={`mt-1 ${hintCls}`}>
              Live readings from the API host. Each parallel job runs in its own worker process; workers use multiple
              threads internally (Polars / reconciliation).
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                theme={theme}
                label="CPU"
                value={`${cpuCores ?? '?'} logical cores`}
                sub={
                  projection.coresPerJobApprox != null
                    ? `~${projection.coresPerJobApprox} cores/job equiv. at ${projection.jobs} parallel`
                    : 'Core count from os.cpu_count()'
                }
              />
              <MetricCard
                theme={theme}
                label="RAM"
                value={
                  <>
                    {ra.system?.available_ram_gib ?? '?'}
                    <span className="text-sm font-normal opacity-70"> / {ra.system?.total_ram_gib ?? '?'} GiB free</span>
                  </>
                }
                sub={`System RAM in use: ${formatPct(1 - (ra.system?.available_ram_bytes ?? 0) / Math.max(1, ra.system?.total_ram_bytes ?? 1)) ?? '—'}`}
              >
                <UsageBar fraction={projection.ramUsedSystemPct} theme={theme} />
              </MetricCard>
              <MetricCard
                theme={theme}
                label="Disk (workspace)"
                value={
                  <>
                    {ra.system?.available_disk_gib ?? '?'}
                    <span className="text-sm font-normal opacity-70"> / {ra.system?.total_disk_gib ?? '?'} GiB free</span>
                  </>
                }
                sub="Spill partitions & temp files use this volume"
              >
                <UsageBar fraction={projection.diskUsedSystemPct} theme={theme} />
              </MetricCard>
              <MetricCard
                theme={theme}
                label="Swap"
                value={swapLabel(swapPressure)}
                sub={
                  swapPressure != null
                    ? `${formatPct(swapPressure)} of swap in use — high swap slows validations`
                    : 'Swap stats unavailable on this host'
                }
              />
            </div>
          </div>

          <div
            className={
              theme === 'dark'
                ? 'rounded-lg border border-white/10 bg-white/5 px-4 py-3'
                : 'rounded-lg border border-blue-100 bg-blue-50/80 px-4 py-3'
            }
          >
            <p className={theme === 'dark' ? 'text-sm font-semibold text-slate-200' : 'text-sm font-semibold text-slate-800'}>
              What the slider controls
            </p>
            <p className={`mt-1.5 ${hintCls}`}>
              Three controls: parallel jobs, threads per worker, and disk headroom per job. Applied when each worker
              starts.
            </p>
          </div>

          <div>
            <h3 className={sectionTitle}>1. Parallel jobs</h3>
            <p className={`mt-1 ${hintCls}`}>
              Left = one validation at a time (serial). Right = more overlap; use &quot;Use recommended&quot; for a safe
              default ({recommended ?? '?'} on this host).
            </p>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <label
                className={theme === 'dark' ? 'text-sm font-semibold text-slate-200' : 'text-sm font-semibold text-slate-700'}
                htmlFor="pegasus-parallel-jobs-range"
              >
                Max parallel jobs
              </label>
              <div className="flex items-center gap-2">
                {projection.recommended != null && concurrencySlider !== projection.recommended ? (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onConcurrencyChange(projection.recommended)}
                    className={
                      theme === 'dark'
                        ? 'rounded bg-white/10 px-2 py-1 text-xs font-semibold text-slate-200 hover:bg-white/15'
                        : 'rounded bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 hover:bg-blue-200'
                    }
                  >
                    Use recommended ({projection.recommended})
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
              <span>1 (serial — one job at a time)</span>
              <span>up to {sliderMax}</span>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <LimitBadge label="Advisor max (RAM)" value={ra.limits?.max_safe_by_ram} theme={theme} color="blue" />
              <LimitBadge label="Advisor max (disk)" value={ra.limits?.max_safe_by_disk} theme={theme} color="emerald" />
              <LimitBadge label="Advisor max (CPU)" value={ra.limits?.max_safe_by_cpu} theme={theme} color="purple" />
              {projection.recommended != null ? (
                <LimitBadge label="Recommended" value={projection.recommended} theme={theme} color="accent" />
              ) : null}
            </div>

            {autoTuneEnabled && effectiveMax != null && effectiveMax < concurrencySlider ? (
              <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
                Auto-tune active: effective cap is <strong>{effectiveMax}</strong> (your setting is {concurrencySlider}).
                Projections below use the effective cap.
              </p>
            ) : null}
          </div>

          <div>
            <h3 className={sectionTitle}>2. CPU threads per job</h3>
            <ResourceSlider
              id="pegasus-threads-per-job"
              label="Threads per validation worker"
              hint={`Partition compare parallelism inside one job. Auto uses all ${cpuCores ?? '?'} cores when set to 0.`}
              min={0}
              max={cpuCores ?? 8}
              step={1}
              value={threadsPerJob ?? 0}
              displayValue={threadsPerJob === 0 ? `Auto (${cpuCores ?? '?'})` : String(threadsPerJob)}
              disabled={disabled || onThreadsPerJobChange == null}
              theme={theme}
              onChange={(n) => onThreadsPerJobChange?.(n)}
              leftLabel="0 (auto)"
              rightLabel={`${cpuCores ?? '?'} max`}
            />
          </div>

          <div>
            <h3 className={sectionTitle}>3. Disk headroom per job</h3>
            <ResourceSlider
              id="pegasus-disk-headroom"
              label="Disk multiplier"
              hint="Required free disk before spill ≥ multiplier × (source + target CSV size)."
              min={1}
              max={5}
              step={0.1}
              value={diskHeadroomMultiplier ?? 1.5}
              displayValue={`${Number(diskHeadroomMultiplier ?? 1.5).toFixed(1)}×`}
              disabled={disabled || onDiskHeadroomMultiplierChange == null}
              theme={theme}
              onChange={(n) => onDiskHeadroomMultiplierChange?.(Math.round(n * 10) / 10)}
              leftLabel="1.0× (minimal)"
              rightLabel="5.0× (conservative)"
            />
          </div>

          <div>
            <h3 className={sectionTitle}>Estimated resource use at your setting</h3>
            <p className={`mt-1 ${hintCls}`}>
              Based on typical CSV sizes in the queue (or defaults). Actual use varies with file size and reconciliation
              path (in-memory vs spill).
            </p>
            <div className={`mt-3 ${tableWrap}`}>
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className={thCls}>Resource</th>
                    <th className={thCls}>Per job</th>
                    <th className={thCls}>× {projection.jobs} parallel</th>
                    <th className={thCls}>vs available</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className={tdCls}>RAM (new jobs)</td>
                    <td className={tdMono}>{formatMiB(projection.perJobRam)}</td>
                    <td className={tdMono}>{formatGiB(projection.projectedNewRam)}</td>
                    <td className={tdCls}>
                      {formatPct(projection.ramShareOfAvailable) ?? '—'} of {ra.system?.available_ram_gib ?? '?'} GiB free
                      <UsageBar fraction={projection.ramShareOfAvailable} theme={theme} />
                    </td>
                  </tr>
                  {projection.runningCount > 0 ? (
                    <tr>
                      <td className={tdCls}>RAM (already running)</td>
                      <td className={tdMono}>—</td>
                      <td className={tdMono}>{formatGiB(projection.runningRam)}</td>
                      <td className={tdCls}>{projection.runningCount} job(s) in flight</td>
                    </tr>
                  ) : null}
                  <tr>
                    <td className={tdCls}>Disk spill / temp</td>
                    <td className={tdMono}>{formatMiB(projection.perJobDisk)}</td>
                    <td className={tdMono}>{formatGiB(projection.projectedDisk)}</td>
                    <td className={tdCls}>
                      {formatPct(projection.diskShareOfAvailable) ?? '—'} of {ra.system?.available_disk_gib ?? '?'} GiB free
                      <UsageBar fraction={projection.diskShareOfAvailable} theme={theme} />
                    </td>
                  </tr>
                  <tr>
                    <td className={tdCls}>CPU sharing</td>
                    <td className={tdMono}>multi-threaded</td>
                    <td className={tdMono}>
                      {projection.jobs} worker{projection.jobs === 1 ? '' : 's'}
                    </td>
                    <td className={tdCls}>
                      {projection.totalThreadDemand != null && cpuCores != null ? (
                        <>
                          ~{projection.totalThreadDemand} thread slots ({projection.jobs}×{projection.coresPerJobApprox})
                          on {cpuCores} cores
                        </>
                      ) : projection.coresPerJobApprox != null ? (
                        <>{projection.coresPerJobApprox} threads per worker</>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

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

          <label className="flex cursor-pointer items-start gap-3">
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
              <p className={hintCls}>
                When enabled, the server lowers the effective parallel cap if RAM, disk, or swap pressure is too high —
                even if you set a higher number above.
              </p>
            </div>
          </label>
        </>
      ) : null}
    </div>
  )
}

function LimitBadge({ label, value, theme, color }) {
  const colors = {
    blue: theme === 'dark' ? 'bg-blue-500/20 text-blue-200' : 'bg-blue-100 text-blue-700',
    emerald: theme === 'dark' ? 'bg-emerald-500/20 text-emerald-200' : 'bg-emerald-100 text-emerald-700',
    purple: theme === 'dark' ? 'bg-purple-500/20 text-purple-200' : 'bg-purple-100 text-purple-700',
    accent: theme === 'dark' ? 'bg-[#EB4C4C]/20 text-[#f08080]' : 'bg-[#FDE8E8] text-[#EB4C4C]',
  }
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${colors[color] ?? colors.blue}`}>
      {label}: {value ?? '?'}
    </span>
  )
}
