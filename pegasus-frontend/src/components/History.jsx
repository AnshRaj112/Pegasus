export default function History() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      minHeight: 320, padding: '48px 24px', textAlign: 'center',
      background: 'var(--surface-1)', border: '1px solid var(--border-1)', borderRadius: 12,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 10,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--surface-3)', color: 'var(--text-3)',
        border: '1px solid var(--border-2)', marginBottom: 14,
      }}>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.4"/>
          <path d="M10 6v4l2.5 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-1)', letterSpacing: '-0.02em', marginBottom: 4 }}>
        History
      </h2>
      <p style={{ fontSize: 13, color: 'var(--text-3)', maxWidth: 300, lineHeight: 1.5, marginBottom: 4 }}>
        Your validation runs and saved drafts will appear here.
      </p>
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        fontSize: 11, fontWeight: 500, color: 'var(--text-4)',
        padding: '3px 9px', borderRadius: 4,
        background: 'var(--surface-3)', border: '1px solid var(--border-1)',
      }}>
        Coming soon
      </span>
    </div>
  )
}
