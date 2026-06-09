/**
 * Live validation job status — queue position, chunk/row progress, parallel workers.
 */

function formatPercent(n: number | null | undefined) {
  if (!Number.isFinite(n)) return null
  return `${Math.max(0, Math.min(100, Number(n))).toFixed(1)}%`
}

function formatInt(n: unknown) {
  const value = Number(n)
  if (!Number.isFinite(value)) return '—'
  return value.toLocaleString()
}

function sideLabel(status: string | undefined) {
  if (status === 'done') return 'done'
  if (status === 'active') return 'running'
  return 'waiting'
}

function SideProgressBlock({ title, side }: { title: string; side?: Record<string, unknown> }) {
  if (!side) return null
  const status = typeof side.status === 'string' ? side.status : 'pending'
  return (
    <div
      style={{
        flex: '1 1 220px',
        padding: '10px 12px',
        borderRadius: 8,
        background: 'var(--surface-1, #fff)',
        border: '1px solid var(--border-1, #e2e8f0)',
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)', marginBottom: 6 }}>
        {title}{' '}
        <span style={{ fontWeight: 500, color: 'var(--text-3)' }}>({sideLabel(status)})</span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-3)', lineHeight: 1.6 }}>
        <div>Rows processed: <strong>{formatInt(side.rows_processed)}</strong></div>
        <div>Chunks completed: <strong>{formatInt(side.chunks_completed)}</strong></div>
        {Number(side.current_chunk_rows) > 0 ? (
          <div>Current chunk: <strong>{formatInt(side.current_chunk_rows)}</strong> rows</div>
        ) : null}
      </div>
    </div>
  )
}

export default function ValidationJobProgress({
  phase,
  jobId,
  message,
  progress = {},
  elapsedLabel,
  variant = 'default',
}) {
  const pct = formatPercent(progress.percent)
  const live = progress.live && typeof progress.live === 'object' ? progress.live : null
  const queuePos = progress.queue_position
  const pendingAhead = progress.pending_ahead
  const runningJobs = progress.running_jobs
  const maxConcurrency = progress.max_concurrency

  const isCompact = variant === 'compact'
  const wrapStyle = isCompact
    ? {
        marginBottom: 12,
        padding: '11px 14px',
        borderRadius: 9,
        background: 'var(--accent-muted)',
        border: '1px solid var(--accent-border)',
      }
    : {
        marginBottom: 16,
        padding: '14px 16px',
        borderRadius: 10,
        background: 'var(--surface-2)',
        border: '1px solid var(--border-1)',
      }

  const title =
    phase === 'queued' ? 'Queued — waiting for a worker slot'
      : phase === 'accepted' ? 'Job accepted — starting worker'
        : phase === 'uploading' || phase === 'upload' ? 'Uploading files'
          : phase === 'partitioning' ? 'Partitioning files into spill buckets'
            : phase === 'reconciling' ? 'Reconciling partitions'
              : phase === 'running' || phase === 'validating' ? 'Validation in progress'
                : 'Working…'

  const pipelinePhase = live && typeof live.pipeline_phase === 'string' ? live.pipeline_phase : null

  return (
    <div style={wrapStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span
          style={{
            width: 14,
            height: 14,
            borderRadius: '50%',
            border: '2px solid var(--accent-border)',
            borderTopColor: 'var(--accent)',
            animation: 'spin 0.7s linear infinite',
            flexShrink: 0,
          }}
        />
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-1)' }}>{title}</span>
        {elapsedLabel ? (
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-3)', fontFamily: 'Geist Mono, monospace' }}>
            {elapsedLabel}
          </span>
        ) : null}
      </div>

      {message ? (
        <p style={{ margin: '0 0 10px', fontSize: 13, color: 'var(--text-2)', lineHeight: 1.45 }}>{message}</p>
      ) : null}

      {pct ? (
        <div style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-3)', marginBottom: 4 }}>
            <span>Overall progress</span>
            <strong style={{ color: 'var(--text-2)' }}>{pct}</strong>
          </div>
          <div style={{ height: 8, borderRadius: 999, background: 'var(--border-1, #e2e8f0)', overflow: 'hidden' }}>
            <div
              style={{
                width: pct,
                height: '100%',
                borderRadius: 999,
                background: 'var(--accent, #EB4C4C)',
                transition: 'width 0.35s ease',
              }}
            />
          </div>
        </div>
      ) : null}

      {live ? (
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 12, color: 'var(--text-3)', display: 'flex', flexWrap: 'wrap', gap: '8px 14px', marginBottom: 10 }}>
            {live.column_count != null ? <span>Columns: <strong>{formatInt(live.column_count)}</strong></span> : null}
            {live.chunk_rows != null ? <span>Chunk size: <strong>{formatInt(live.chunk_rows)}</strong> rows</span> : null}
            {live.partition_buckets != null ? <span>Partition buckets: <strong>{formatInt(live.partition_buckets)}</strong></span> : null}
            {live.partition_parallel_workers != null ? (
              <span>Read parallelism: <strong>{formatInt(live.partition_parallel_workers)}</strong> (source + target)</span>
            ) : null}
            {pipelinePhase === 'reconcile' && live.reconcile_parallel_workers != null ? (
              <span>Reconcile workers: <strong>{formatInt(live.reconcile_parallel_workers)}</strong></span>
            ) : null}
          </div>

          {pipelinePhase === 'partition' ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              <SideProgressBlock title="Source" side={live.source} />
              <SideProgressBlock title="Target" side={live.target} />
            </div>
          ) : null}

          {pipelinePhase === 'reconcile' && live.reconcile ? (
            <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
              Partitions reconciled:{' '}
              <strong>
                {formatInt(live.reconcile.partitions_done)} / {formatInt(live.reconcile.partitions_total)}
              </strong>
            </div>
          ) : null}
        </div>
      ) : null}

      <div style={{ fontSize: 12, color: 'var(--text-3)', display: 'flex', flexWrap: 'wrap', gap: '8px 16px' }}>
        {jobId ? <span>Job <code style={{ fontSize: 11 }}>{jobId}</code></span> : null}
        {phase ? <span>Phase: <strong>{phase}</strong></span> : null}
        {queuePos != null ? (
          <span>
            Queue position: <strong>{Number(queuePos) + 1}</strong>
            {pendingAhead != null ? ` (${pendingAhead} ahead)` : ''}
          </span>
        ) : null}
        {runningJobs != null && maxConcurrency != null ? (
          <span>Job queue: <strong>{runningJobs}</strong> / {maxConcurrency} slots</span>
        ) : null}
      </div>

      <p style={{ margin: '10px 0 0', fontSize: 12, color: 'var(--text-4)' }}>
        Large files often take several minutes. Keep this tab open while chunks are processed.
      </p>
    </div>
  )
}
