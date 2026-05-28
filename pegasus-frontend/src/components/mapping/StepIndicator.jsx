const STEPS = [
  { id: 1, label: 'Select File Type',    desc: 'CSV, ZIP or Fixed-Width' },
  { id: 2, label: 'Select Files',        desc: 'Source & target'    },
  { id: 3, label: 'Configure Mapping',   desc: 'Map layouts & bounds'},
  { id: 4, label: 'Review & Run',        desc: 'Validate or draft'  },
]

export default function StepIndicator({ currentStep }) {
  return (
    <div style={{ display: 'flex', alignItems: 'stretch', gap: 0 }}>
      {STEPS.map((step, i) => {
        const done    = currentStep > step.id
        const active  = currentStep === step.id
        const upcoming = currentStep < step.id

        return (
          <div
            key={step.id}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '14px 16px',
              borderRight: i < STEPS.length - 1 ? '1px solid var(--border-1)' : 'none',
              borderTop: active ? '2px solid var(--accent)' : '2px solid transparent',
              background: active ? 'rgba(249,115,22,0.04)' : 'transparent',
              transition: 'all 0.2s',
            }}
          >
            {/* Number or check */}
            <div style={{
              width: 22,
              height: 22,
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              fontSize: 11,
              fontWeight: 700,
              fontFamily: 'Geist Mono, monospace',
              background: done
                ? 'var(--success)'
                : active
                ? 'var(--accent)'
                : 'var(--surface-3)',
              color: done || active ? '#fff' : 'var(--text-3)',
              border: upcoming ? '1px solid var(--border-2)' : 'none',
            }}>
              {done ? (
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                  <path d="M2 5l2 2 4-4" stroke="white" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              ) : step.id}
            </div>

            {/* Labels */}
            <div>
              <div style={{
                fontSize: 13,
                fontWeight: active ? 600 : 400,
                color: upcoming ? 'var(--text-3)' : 'var(--text-1)',
                letterSpacing: '-0.01em',
                lineHeight: 1.2,
              }}>
                {step.label}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 1 }}>
                {step.desc}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
