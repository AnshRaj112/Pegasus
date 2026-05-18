import React, { useState } from 'react'

function TabButton({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={active ? 'px-4 py-2 rounded-xl bg-slate-900 text-white' : 'px-4 py-2 rounded-xl bg-white border'}
      style={{ border: '1px solid var(--border-1)', cursor: 'pointer' }}
    >
      {children}
    </button>
  )
}

function PlaceholderBox({ title, children }) {
  return (
    <div style={{
      marginTop: 12,
      padding: 18,
      borderRadius: 12,
      background: 'var(--surface-1)',
      border: '1px solid var(--border-1)'
    }}>
      <h4 style={{ margin: 0, marginBottom: 8, color: 'var(--text-1)', fontSize: 15 }}>{title}</h4>
      <div style={{ color: 'var(--text-3)', fontSize: 13 }}>{children}</div>
    </div>
  )
}

export default function History() {
  const [topTab, setTopTab] = useState('mapping')
  const [validationTab, setValidationTab] = useState('incremental')

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <TabButton active={topTab === 'mapping'} onClick={() => setTopTab('mapping')}>Mapping History</TabButton>
        <TabButton active={topTab === 'validation'} onClick={() => setTopTab('validation')}>Validation History</TabButton>
      </div>

      {topTab === 'mapping' ? (
        <div>
          <PlaceholderBox title="Mapping History">
            <p style={{ marginTop: 0 }}>Saved mappings, templates and mapping edits will appear here.</p>
            <p style={{ marginBottom: 0, color: 'var(--text-4)' }}>No mapping history available yet.</p>
          </PlaceholderBox>
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <TabButton active={validationTab === 'incremental'} onClick={() => setValidationTab('incremental')}>Incremental</TabButton>
            <TabButton active={validationTab === 'historical'} onClick={() => setValidationTab('historical')}>Historical</TabButton>
          </div>

          {validationTab === 'incremental' ? (
            <PlaceholderBox title="Incremental Validation History">
              <p style={{ marginTop: 0 }}>Recent incremental runs (fast, delta-only) will be listed here.</p>
              <p style={{ marginBottom: 0, color: 'var(--text-4)' }}>No incremental validations recorded.</p>
            </PlaceholderBox>
          ) : (
            <PlaceholderBox title="Historical Validation History">
              <p style={{ marginTop: 0 }}>Full historical runs and archives will be listed here.</p>
              <p style={{ marginBottom: 0, color: 'var(--text-4)' }}>No historical validations recorded.</p>
            </PlaceholderBox>
          )}
        </div>
      )}
    </div>
  )
}
