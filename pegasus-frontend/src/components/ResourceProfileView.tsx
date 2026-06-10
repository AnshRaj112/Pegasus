type Snapshot = {
  label?: string
  memory?: {
    available_gib?: number
    used_gib?: number
    process_rss_mib?: number | null
  }
  disk?: {
    available_gib?: number
    used_gib?: number
    job_workspace_mib?: number
  }
  cpu?: {
    system_percent?: number | null
    process_percent?: number | null
    cores?: number
  }
}

function formatGiB(value: number | null | undefined) {
  if (!Number.isFinite(value)) return '—'
  return `${Number(value).toFixed(2)} GiB`
}

function formatMiB(value: number | null | undefined) {
  if (!Number.isFinite(value)) return '—'
  return `${Number(value).toFixed(1)} MiB`
}

function formatPercent(value: number | null | undefined) {
  if (!Number.isFinite(value)) return '—'
  return `${Number(value).toFixed(1)}%`
}

function SnapshotRow({ title, snapshot }: { title: string; snapshot?: Snapshot | null }) {
  if (!snapshot) return null
  return (
    <div style={{
      padding: '10px 12px',
      borderRadius: 8,
      border: '1px solid var(--border-1)',
      background: 'var(--surface-1)',
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-1)', marginBottom: 8 }}>{title}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, fontSize: 11, color: 'var(--text-3)' }}>
        <div>
          <div>RAM available</div>
          <strong style={{ color: 'var(--text-1)' }}>{formatGiB(snapshot.memory?.available_gib)}</strong>
        </div>
        <div>
          <div>RAM used</div>
          <strong style={{ color: 'var(--text-1)' }}>{formatGiB(snapshot.memory?.used_gib)}</strong>
        </div>
        <div>
          <div>Process RSS</div>
          <strong style={{ color: 'var(--text-1)' }}>{formatMiB(snapshot.memory?.process_rss_mib)}</strong>
        </div>
        <div>
          <div>Disk free</div>
          <strong style={{ color: 'var(--text-1)' }}>{formatGiB(snapshot.disk?.available_gib)}</strong>
        </div>
        <div>
          <div>Job workspace</div>
          <strong style={{ color: 'var(--text-1)' }}>{formatMiB(snapshot.disk?.job_workspace_mib)}</strong>
        </div>
        <div>
          <div>CPU (proc / sys)</div>
          <strong style={{ color: 'var(--text-1)' }}>
            {formatPercent(snapshot.cpu?.process_percent)} / {formatPercent(snapshot.cpu?.system_percent)}
          </strong>
        </div>
      </div>
    </div>
  )
}

export default function ResourceProfileView({
  profile,
  compact = false,
}: {
  profile?: Record<string, unknown> | null
  compact?: boolean
}) {
  if (!profile || typeof profile !== 'object') {
    return (
      <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
        Resource profile will appear once the job starts reporting metrics.
      </div>
    )
  }

  const before = profile.before as Snapshot | undefined
  const during = Array.isArray(profile.during) ? profile.during as Snapshot[] : []
  const latest = (profile.latest || during[during.length - 1]) as Snapshot | undefined
  const after = profile.after as Snapshot | undefined
  const peak = profile.peak as Record<string, unknown> | undefined

  if (compact) {
    const snap = latest || before
    return (
      <div style={{ fontSize: 11, color: 'var(--text-3)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <span>RSS {formatMiB(snap?.memory?.process_rss_mib as number | undefined)}</span>
        <span>Workspace {formatMiB(snap?.disk?.job_workspace_mib)}</span>
        <span>CPU {formatPercent(snap?.cpu?.process_percent)}</span>
        {peak?.process_rss_mib ? <span>Peak RSS {formatMiB(peak.process_rss_mib as number)}</span> : null}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-4)' }}>
        Resource footprint report
      </div>
      <SnapshotRow title="Before validation" snapshot={before} />
      <SnapshotRow title="During validation (latest)" snapshot={latest} />
      <SnapshotRow title="After validation" snapshot={after} />
      {peak && Object.keys(peak).length > 0 ? (
        <div style={{ fontSize: 11, color: 'var(--text-3)' }}>
          Peak RSS {formatMiB(peak.process_rss_mib as number | undefined)},
          peak workspace {formatMiB(peak.job_workspace_mib as number | undefined)},
          peak CPU {formatPercent(peak.process_percent as number | undefined)}
        </div>
      ) : null}
    </div>
  )
}
