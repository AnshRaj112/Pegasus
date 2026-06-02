import { useBackendHealth } from '../hooks/useBackendHealth.js'

/**
 * Global banner when the Pegasus API is unreachable (backend crashed, Docker stopped, 502).
 */
export default function BackendStatusBanner() {
  const { status, isDown, lastError } = useBackendHealth()

  if (status === 'checking' || !isDown) {
    return null
  }

  return (
    <div
      role="alert"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 200,
        padding: '10px 16px',
        background: 'var(--danger, #b91c1c)',
        color: '#fff',
        fontSize: 13,
        fontWeight: 500,
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
      }}
    >
      <span style={{ flex: 1, lineHeight: 1.45 }}>
        <strong>Backend unavailable.</strong>{' '}
        {lastError || 'The API did not respond to health checks.'}
        {' '}
        Large validations can stop the server if it runs out of memory. Restart with{' '}
        <code style={{ background: 'rgba(0,0,0,0.2)', padding: '1px 6px', borderRadius: 4 }}>
          docker compose up -d backend
        </code>
        {' '}and watch logs:{' '}
        <code style={{ background: 'rgba(0,0,0,0.2)', padding: '1px 6px', borderRadius: 4 }}>
          docker compose logs -f backend
        </code>
      </span>
    </div>
  )
}
