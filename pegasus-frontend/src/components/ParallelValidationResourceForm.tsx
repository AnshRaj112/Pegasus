import { Alert, Button, Checkbox, InputNumber, Slider, Space, Tag, Typography } from 'antd'

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

  const userCap = Math.max(0, Math.floor(concurrencySlider) || 0)
  const effectiveMax = queueInfo?.effective_max_concurrency
  let jobs = userCap > 0 ? userCap : Math.max(1, effectiveMax ?? 1)
  if (autoTuneEnabled && effectiveMax != null) {
    jobs = userCap > 0 ? Math.min(jobs, Math.max(1, effectiveMax)) : Math.max(1, effectiveMax)
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
    concurrencySlider || 0,
    queueInfo?.max_concurrency ?? 0,
    cpuCores ?? 1,
    recommended ?? 1,
    practicalSliderMax,
  )
  const isAutoCap = concurrencySlider <= 0
  const isDark = theme === 'dark'
  const hintColor = isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.6)'
  const labelColor = isDark ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.88)'

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {queueLoading ? (
        <Typography.Text style={{ color: hintColor }}>Loading server resources…</Typography.Text>
      ) : null}

      {queueError ? (
        <Alert
          type="error"
          showIcon
          message={queueError}
          action={
            onRefresh ? (
              <Button type="link" size="small" onClick={onRefresh} style={{ paddingInline: 0 }}>
                Retry
              </Button>
            ) : undefined
          }
        />
      ) : null}

      {!queueLoading && ra ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          {showQueueStatus && queueInfo ? (
            <Space
              wrap
              size={[8, 8]}
              style={{
                width: '100%',
                padding: '12px 16px',
                borderRadius: 8,
                border: isDark ? '1px solid rgba(255,255,255,0.12)' : '1px solid #d9d9d9',
                background: isDark ? 'rgba(255,255,255,0.04)' : '#fafafa',
              }}
            >
              <Tag color={isDark ? 'default' : 'processing'}>
                Queue: {queueInfo.pending ?? 0} pending · {queueInfo.running ?? 0} running
              </Tag>
              {effectiveMax != null && autoTuneEnabled && (isAutoCap || effectiveMax < concurrencySlider) ? (
                <Tag color="gold">
                  {isAutoCap ? `Auto: up to ${effectiveMax} parallel` : `Effective cap: ${effectiveMax} (auto-tune)`}
                </Tag>
              ) : null}
            </Space>
          ) : null}

          <Typography.Paragraph style={{ marginBottom: 0, color: hintColor }}>
            {cpuCores ?? '?'} CPU cores · {projection.ramFreeGib ?? '?'} GiB RAM free · {projection.diskFreeGib ?? '?'} GiB disk free.
            {recommended != null ? (
              <>
                {' '}
                Server recommends <Typography.Text strong>{recommended}</Typography.Text> parallel job{recommended === 1 ? '' : 's'}.
              </>
            ) : null}
          </Typography.Paragraph>

          <div>
            <Typography.Title level={5} style={{ marginTop: 0, marginBottom: 4, color: labelColor }}>
              Max parallel jobs
            </Typography.Title>
            <Typography.Text style={{ color: hintColor }}>
              How many validations may run at once. Choose Auto to run every job in parallel until RAM, disk, or CPU
              limits are reached — extra jobs are scheduled in the queue.
            </Typography.Text>

            <Space wrap align="center" style={{ width: '100%', marginTop: 16, justifyContent: 'space-between' }}>
              <Typography.Text strong style={{ color: labelColor }}>
                Parallel jobs
              </Typography.Text>
              <Space align="center" size={8}>
                {recommended != null && concurrencySlider !== recommended ? (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onConcurrencyChange(recommended)}
                    style={{
                      border: 'none',
                      borderRadius: 6,
                      padding: '4px 10px',
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: disabled ? 'not-allowed' : 'pointer',
                      background: isDark ? 'rgba(255,255,255,0.08)' : '#e6f4ff',
                      color: isDark ? '#f5f5f5' : '#1677ff',
                    }}
                  >
                    Use recommended ({recommended})
                  </button>
                ) : null}
                <InputNumber
                  min={0}
                  value={concurrencySlider}
                  disabled={disabled}
                  onChange={(value) => {
                    const n = Number(value)
                    if (Number.isFinite(n) && n >= 0) onConcurrencyChange(Math.floor(n))
                  }}
                  style={{ width: 96, textAlign: 'center' }}
                  aria-label="Max parallel jobs"
                  controls={false}
                />
              </Space>
            </Space>

            <div style={{ marginTop: 8 }}>
              <Slider
                id="pegasus-parallel-jobs-range"
                min={0}
                max={sliderMax}
                step={1}
                value={Math.min(Math.max(0, concurrencySlider), sliderMax)}
                disabled={disabled}
                onChange={(value) => onConcurrencyChange(Number(value))}
              />
            </div>
            <Typography.Text style={{ display: 'flex', justifyContent: 'space-between', color: hintColor }}>
              <span>Auto (resource-based)</span>
              <span>up to {sliderMax}</span>
            </Typography.Text>
          </div>

          <Checkbox
            checked={autoTuneEnabled}
            disabled={disabled}
            onChange={(ev) => onAutoTuneChange(ev.target.checked)}
            style={{ alignItems: 'flex-start' }}
          >
            <span style={{ display: 'block', color: labelColor, fontWeight: 600 }}>Auto-tune</span>
            <Typography.Paragraph style={{ marginBottom: 0, marginTop: 4, color: hintColor }}>
              When on, jobs start immediately while resources allow; only overflow goes to the schedule queue. When off,
              only your parallel cap is used (Auto uses CPU core count).
            </Typography.Paragraph>
          </Checkbox>

          {ra.warnings?.length ? (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {ra.warnings.map((w, i) => (
                <Alert key={i} type="warning" showIcon message={w} />
              ))}
            </Space>
          ) : null}
        </Space>
      ) : null}
    </Space>
  )
}