/** Small control to open per-column compare rules. */
export default function CompareRuleIconButton({
  active = false,
  configured = false,
  onClick,
  label = 'Compare rules',
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={configured ? `Edit ${label}` : label}
      aria-label={label}
      aria-pressed={active}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 26,
        height: 26,
        flexShrink: 0,
        borderRadius: 6,
        border: '1px solid',
        borderColor: active || configured ? 'var(--accent-border)' : 'var(--border-2)',
        background: active || configured ? 'var(--accent-muted)' : 'var(--surface-1)',
        color: active || configured ? 'var(--accent)' : 'var(--text-3)',
        cursor: 'pointer',
        padding: 0,
        boxShadow: active ? '0 0 0 2px var(--accent-muted)' : 'none',
      }}
    >
      <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden>
        <path
          d="M7 1.4l.85 2.55 2.55.85-2.55.85L7 8.3l-.85-2.55-2.55-.85 2.55-.85L7 1.4z"
          stroke="currentColor"
          strokeWidth="1.15"
          strokeLinejoin="round"
        />
        <path d="M11.4 9.4v2.8M9.9 10.9h3" stroke="currentColor" strokeWidth="1.15" strokeLinecap="round" />
      </svg>
    </button>
  )
}
