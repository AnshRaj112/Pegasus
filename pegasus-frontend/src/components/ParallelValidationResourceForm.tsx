import React from 'react'
import { Slider, Switch, InputNumber, Space, Typography, Alert, Button, Badge, Card, Tag } from 'antd'

const { Text, Paragraph } = Typography

export function buildResourceProjection(queueInfo: any, concurrencySlider: number, autoTuneEnabled: boolean) {
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

interface ParallelValidationResourceFormProps {
  queueInfo: any
  queueLoading?: boolean
  queueError?: string
  concurrencySlider: number
  onConcurrencyChange: (val: number) => void
  autoTuneEnabled: boolean
  onAutoTuneChange: (val: boolean) => void
  onRefresh?: () => void
  disabled?: boolean
  theme?: 'light' | 'dark'
  showQueueStatus?: boolean
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
}: ParallelValidationResourceFormProps) {
  const ra = queueInfo?.resource_advisor ?? null
  const cpuCores = queueInfo?.cpu_cores_available ?? ra?.system?.cpu_cores ?? null
  const effectiveMax = queueInfo?.effective_max_concurrency ?? null
  const projection = buildResourceProjection(queueInfo, concurrencySlider, autoTuneEnabled)
  const recommended = projection.recommended

  const practicalSliderMax = Math.min(
    32,
    ra?.limits?.max_safe_by_cpu ?? cpuCores ?? 32,
    recommended != null ? Math.max(recommended, cpuCores ?? 1) : cpuCores ?? 8
  )
  const sliderMax = Math.max(
    1,
    concurrencySlider,
    queueInfo?.max_concurrency ?? 1,
    cpuCores ?? 1,
    recommended ?? 1,
    practicalSliderMax
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {queueLoading && (
        <Text type="secondary">Loading server resource parameters…</Text>
      )}

      {queueError && (
        <Alert
          message={
            <span>
              {queueError}
              {onRefresh && (
                <Button type="link" size="small" onClick={onRefresh} style={{ padding: 0, marginLeft: '8px' }}>
                  Retry
                </Button>
              )}
            </span>
          }
          type="error"
          showIcon
        />
      )}

      {!queueLoading && ra && (
        <>
          {showQueueStatus && queueInfo && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', padding: '12px', background: '#f5f5f5', borderRadius: '8px' }}>
              <div>
                <Text strong>Queue Status: </Text>
                <Text>{queueInfo.pending ?? 0} pending · {queueInfo.running ?? 0} running</Text>
              </div>
              {effectiveMax != null && autoTuneEnabled && effectiveMax < concurrencySlider && (
                <div>
                  <Text strong style={{ marginLeft: '12px' }}>Effective Limit: </Text>
                  <Tag color="warning">{effectiveMax} (auto-tuned)</Tag>
                </div>
              )}
            </div>
          )}

          <div>
            <Text type="secondary" style={{ fontSize: '13px' }}>
              System: {cpuCores ?? '?'} CPU cores · {projection.ramFreeGib ?? '?'} GiB RAM free · {projection.diskFreeGib ?? '?'} GiB disk free.
            </Text>
            {recommended != null && (
              <Paragraph style={{ margin: '4px 0 0 0', fontWeight: 600 }}>
                Server recommends {recommended} parallel job{recommended === 1 ? '' : 's'}.
              </Paragraph>
            )}
          </div>

          {/* Slider and Input Block */}
          <div style={{ border: '1px solid #f0f0f0', borderRadius: '8px', padding: '16px', background: '#fafafa' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div>
                <Text strong style={{ fontSize: '14px' }}>Max Parallel Jobs</Text>
                <div style={{ fontSize: '12px', color: '#8c8c8c' }}>Number of concurrent background validations</div>
              </div>
              <Space>
                {recommended != null && concurrencySlider !== recommended && (
                  <Button size="small" onClick={() => onConcurrencyChange(recommended)}>
                    Use Recommended ({recommended})
                  </Button>
                )}
                <InputNumber
                  min={1}
                  max={sliderMax}
                  value={concurrencySlider}
                  disabled={disabled}
                  onChange={(val) => {
                    if (val && val >= 1) onConcurrencyChange(Math.floor(val))
                  }}
                  style={{ width: '70px' }}
                />
              </Space>
            </div>
            <Slider
              min={1}
              max={sliderMax}
              value={concurrencySlider}
              disabled={disabled}
              onChange={(val) => onConcurrencyChange(val)}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#8c8c8c' }}>
              <span>1 job</span>
              <span>{sliderMax} jobs max</span>
            </div>
          </div>

          {/* Auto-tune Option */}
          <Card size="small" style={{ borderColor: '#e8e8e8' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
              <Switch
                checked={autoTuneEnabled}
                disabled={disabled}
                onChange={onAutoTuneChange}
                style={{ marginTop: '4px' }}
              />
              <div>
                <Text strong style={{ fontSize: '14px' }}>Auto-tune validation scheduler</Text>
                <Paragraph type="secondary" style={{ fontSize: '12px', margin: '4px 0 0 0' }}>
                  If resources are low on the host server, Pegasus will automatically scale back the number of parallel workers to prevent crash or OOM errors.
                </Paragraph>
              </div>
            </div>
          </Card>

          {ra.warnings?.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
              {ra.warnings.map((warning: string, idx: number) => (
                <Alert key={idx} message={warning} type="warning" showIcon />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
