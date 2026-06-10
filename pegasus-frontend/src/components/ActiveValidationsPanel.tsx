import { Button, Progress, Tag } from 'antd'
import { Activity, Bell, CheckCircle2, XCircle } from 'lucide-react'
import { useValidationRuns } from '../context/ValidationRunsContext'
import ValidationJobProgress from './ValidationJobProgress'
import ResourceProfileView from './ResourceProfileView'

function basename(path: string) {
  const normalized = String(path || '').replace(/\\/g, '/')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || path || 'file'
}

function runDisplay(run: { status: string; outcome?: string | null }) {
  if (run.status === 'failed' || run.outcome === 'failed') {
    return { label: 'job failed', color: 'red' as const }
  }
  if (run.status === 'completed' && run.outcome === 'mismatches') {
    return { label: 'mismatches found', color: 'orange' as const }
  }
  if (run.status === 'completed') {
    return { label: 'passed', color: 'green' as const }
  }
  if (run.status === 'running') return { label: 'running', color: 'blue' as const }
  return { label: 'scheduled', color: 'gold' as const }
}

export default function ActiveValidationsPanel({
  showResourceDetails = true,
  limit,
}: {
  showResourceDetails?: boolean
  limit?: number
}) {
  const {
    runs,
    activeCount,
    focusRun,
    focusedRunId,
    dismissRun,
    queueSnapshot,
  } = useValidationRuns()

  const visibleRuns = typeof limit === 'number' ? runs.slice(0, limit) : runs
  if (visibleRuns.length === 0) {
    return (
      <div className="card" style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <Activity size={18} />
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Active validations</h3>
        </div>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--text-3)' }}>
          No validations are running. Start one from Mapping — you can launch multiple runs in the same tab.
        </p>
      </div>
    )
  }

  const queuePending = Number(queueSnapshot?.pending ?? 0)
  const queueRunning = Number(queueSnapshot?.running ?? 0)

  return (
    <div className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <Activity size={18} />
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Active validations</h3>
            {activeCount > 0 ? <Tag color="processing">{activeCount} running</Tag> : null}
          </div>
          <p style={{ margin: 0, fontSize: 12, color: 'var(--text-3)' }}>
            {queueRunning} running · {queuePending} scheduled (waiting for resources). Notifications fire on completion.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text-3)' }}>
          <Bell size={14} />
          Enable notifications in your browser for completion alerts.
        </div>
      </div>

      {visibleRuns.map((run) => {
        const isActive = run.status === 'queued' || run.status === 'running'
        const percent = Number(run.progress?.percent)
        const display = runDisplay(run)
        const showPercent = Number.isFinite(percent) && percent > 0
        return (
          <div
            key={run.id}
            style={{
              border: `1px solid ${focusedRunId === run.id ? 'var(--accent-border)' : 'var(--border-1)'}`,
              borderRadius: 10,
              padding: 14,
              background: focusedRunId === run.id ? 'var(--accent-muted)' : 'var(--surface-1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                  <Tag color={display.color}>{display.label}</Tag>
                  {run.outcome === 'passed' ? <CheckCircle2 size={14} color="var(--success)" /> : null}
                  {run.outcome === 'failed' ? <XCircle size={14} color="var(--danger)" /> : null}
                  <code style={{ fontSize: 12, color: 'var(--text-2)' }}>
                    {basename(run.sourceLabel)} → {basename(run.targetLabel)}
                  </code>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-4)' }}>Job {run.jobId}</div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <Button size="small" onClick={() => focusRun(run.id)}>Focus</Button>
                {!isActive ? (
                  <Button size="small" type="text" onClick={() => dismissRun(run.id)}>Dismiss</Button>
                ) : null}
              </div>
            </div>

            {isActive ? (
              <ValidationJobProgress
                phase={run.phase || run.status}
                jobId={run.jobId}
                message={run.message}
                progress={run.progress || {}}
                variant="compact"
              />
            ) : (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-3)' }}>
                {run.error
                  || (run.outcome === 'mismatches'
                    ? 'Validation finished — mismatch records were found (this is not a job failure).'
                    : null)
                  || run.message
                  || (run.outcome === 'passed' ? 'Passed with no mismatches' : 'Completed')}
              </div>
            )}

            {showPercent ? (
              <Progress
                percent={Math.max(0, Math.min(100, percent))}
                size="small"
                style={{ marginTop: 10 }}
                status={run.status === 'failed' ? 'exception' : run.status === 'completed' ? 'success' : 'active'}
              />
            ) : null}

            {run.resourceProfile && showResourceDetails ? (
              <div style={{ marginTop: 12 }}>
                <ResourceProfileView profile={run.resourceProfile} />
              </div>
            ) : run.resourceProfile ? (
              <div style={{ marginTop: 12 }}>
                <ResourceProfileView profile={run.resourceProfile} compact />
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
