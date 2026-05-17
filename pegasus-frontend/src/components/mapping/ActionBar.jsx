export default function ActionBar({ onValidate, onSaveAsDraft, isValid, isRunning }) {
  return (
    <div style={{
      marginTop: 24,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
      padding: '14px 18px',
      background: 'var(--surface-1)',
      border: '1px solid var(--border-1)',
      borderRadius: 12,
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-1)', letterSpacing: '-0.01em' }}>
          Ready to run?
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
          Validate instantly, or save as a draft to resume from History.
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
        <button
          type="button"
          onClick={onSaveAsDraft}
          disabled={isRunning}
          className="btn btn-secondary"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M10.5 9v1.5a.5.5 0 01-.5.5H3a.5.5 0 01-.5-.5V9M6.5 2v6M4 5.5l2.5 2.5L9 5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Save draft
        </button>

        <button
          type="button"
          onClick={onValidate}
          disabled={!isValid || isRunning}
          className="btn btn-primary btn-lg"
          style={{ minWidth: 130 }}
        >
          {isRunning ? (
            <>
              <span style={{
                display: 'inline-block',
                width: 13,
                height: 13,
                borderRadius: '50%',
                border: '2px solid rgba(255,255,255,0.25)',
                borderTopColor: '#fff',
                animation: 'spin 0.7s linear infinite',
                flexShrink: 0,
              }} />
              Running…
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M5 3l5 3.5-5 3.5V3z" fill="currentColor"/>
              </svg>
              Run Validation
            </>
          )}
        </button>
      </div>
    </div>
  )
}
