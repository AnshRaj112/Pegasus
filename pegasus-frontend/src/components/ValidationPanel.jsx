import { useEffect, useState } from 'react'
import { MismatchSampleRows } from './MismatchSampleRows'
import './ValidationPanel.css'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

function formatDetail(detail) {
  if (detail == null) return 'Request failed'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((e) => e.msg ?? JSON.stringify(e)).join('; ')
  }
  return JSON.stringify(detail)
}

export function ValidationPanel() {
  const [sourceFile, setSourceFile] = useState(null)
  const [targetFile, setTargetFile] = useState(null)
  const [uidColumn, setUidColumn] = useState('id')
  const [delimiter, setDelimiter] = useState('auto')
  const [phase, setPhase] = useState('idle')
  const [elapsedMs, setElapsedMs] = useState(0)
  const [result, setResult] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')

  const running = phase === 'running'

  useEffect(() => {
    if (!running) return
    const t0 = performance.now()
    const id = setInterval(() => {
      setElapsedMs(Math.round(performance.now() - t0))
    }, 100)
    return () => clearInterval(id)
  }, [running])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!sourceFile || !targetFile) return

    setPhase('running')
    setElapsedMs(0)
    setResult(null)
    setErrorMessage('')

    const body = new FormData()
    body.append('source_file', sourceFile)
    body.append('target_file', targetFile)
    body.append('uid_column', uidColumn.trim())
    body.append('delimiter', delimiter.trim() || 'auto')

    const url = `${apiBase}/api/v1/validate`

    try {
      const res = await fetch(url, {
        method: 'POST',
        body,
      })

      const data = await res.json().catch(() => ({}))

      if (!res.ok) {
        const msg = formatDetail(data.detail)
        throw new Error(msg || `${res.status} ${res.statusText}`)
      }

      setResult(data)
      setPhase('success')
    } catch (err) {
      setPhase('error')
      setErrorMessage(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="validation-panel">
      <p className="validation-lead">
        Upload <strong>source</strong> (expected) and <strong>target</strong>{' '}
        (actual) CSV files. The UI calls{' '}
        <code className="validation-code">POST /api/v1/validate</code> on your
        Pegasus API. Leave delimiter as <code className="validation-code">auto</code>{' '}
        unless you need an override.
      </p>

      <form className="validation-form" onSubmit={handleSubmit}>
        <label className="validation-field">
          <span className="validation-label">Source CSV (expected)</span>
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={running}
            onChange={(ev) => setSourceFile(ev.target.files?.[0] ?? null)}
          />
          {sourceFile ? (
            <span className="validation-file-name">{sourceFile.name}</span>
          ) : null}
        </label>

        <label className="validation-field">
          <span className="validation-label">Target CSV (actual)</span>
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={running}
            onChange={(ev) => setTargetFile(ev.target.files?.[0] ?? null)}
          />
          {targetFile ? (
            <span className="validation-file-name">{targetFile.name}</span>
          ) : null}
        </label>

        <div className="validation-row">
          <label className="validation-field validation-field-grow">
            <span className="validation-label">UID column</span>
            <input
              type="text"
              value={uidColumn}
              disabled={running}
              onChange={(ev) => setUidColumn(ev.target.value)}
              autoComplete="off"
              placeholder="e.g. id"
            />
          </label>
          <label className="validation-field validation-field-narrow">
            <span className="validation-label">Delimiter</span>
            <input
              type="text"
              value={delimiter}
              disabled={running}
              onChange={(ev) => setDelimiter(ev.target.value)}
              className="validation-delimiter"
              title="Use auto, tab, \\t, single-char (, ; |), or multi-char (||, ::)"
              aria-label="CSV delimiter or auto"
              placeholder="auto"
            />
            <span className="validation-field-help">
              Recommended: <code>auto</code>. You can also use <code>tab</code>,{' '}
              <code>\t</code>, <code>|</code>, <code>||</code>, <code>::</code>.
            </span>
          </label>
        </div>

        <button
          type="submit"
          className="validation-submit"
          disabled={running || !sourceFile || !targetFile || !uidColumn.trim()}
        >
          {running ? (
            <>
              <span className="validation-spinner" aria-hidden />
              Running…
            </>
          ) : (
            'Run validation'
          )}
        </button>
      </form>

      <div className="validation-status" role="status" aria-live="polite">
        {running ? (
          <div className="validation-status-running">
            <p className="validation-status-title">Working on the server</p>
            <p className="validation-status-detail">
              Uploading files and comparing rows…{' '}
              <strong>{(elapsedMs / 1000).toFixed(1)}s</strong> elapsed
            </p>
          </div>
        ) : null}

        {phase === 'idle' ? (
          <p className="validation-status-hint">
            Start the API on port <code>8000</code> and use{' '}
            <code>npm run dev</code> so requests proxy to{' '}
            <code>/api</code>.
          </p>
        ) : null}

        {phase === 'success' && result ? (
          <div className="validation-result validation-result-success">
            <p className="validation-status-title">Finished</p>
            <div className="validation-summary-grid">
              <div>
                <span className="validation-metric-label">Match</span>
                <span className="validation-metric-value">
                  {result.summary?.is_match ? 'Yes' : 'No'}
                </span>
              </div>
              <div>
                <span className="validation-metric-label">Source rows</span>
                <span className="validation-metric-value">
                  {result.summary?.source_row_count ?? '—'}
                </span>
              </div>
              <div>
                <span className="validation-metric-label">Target rows</span>
                <span className="validation-metric-value">
                  {result.summary?.target_row_count ?? '—'}
                </span>
              </div>
              <div>
                <span className="validation-metric-label">Mismatch records</span>
                <span className="validation-metric-value">
                  {result.summary?.total_mismatch_records ?? '—'}
                </span>
              </div>
            </div>
            <p className="validation-counts-title">Mismatch counts</p>
            <ul className="validation-counts">
              <li>
                Missing in target:{' '}
                <strong>{result.mismatch_counts?.missing_in_target ?? 0}</strong>
              </li>
              <li>
                Extra in target:{' '}
                <strong>{result.mismatch_counts?.extra_in_target ?? 0}</strong>
              </li>
              <li>
                Value mismatch:{' '}
                <strong>{result.mismatch_counts?.value_mismatch ?? 0}</strong>
              </li>
            </ul>
            {result.run_id ? (
              <p className="validation-run-id">
                Run id: <code>{result.run_id}</code>
              </p>
            ) : null}
            {result.mismatch_samples?.length ? (
              <>
                <p className="validation-samples-title">Sample mismatches</p>
                <div className="validation-table-wrap">
                  <table className="validation-table">
                    <thead>
                      <tr>
                        <th>UID</th>
                        <th>Type</th>
                        <th>Column</th>
                        <th>
                          Expected
                          <span className="validation-th-hint"> (source)</span>
                        </th>
                        <th>
                          Actual
                          <span className="validation-th-hint"> (target)</span>
                        </th>
                      </tr>
                    </thead>
                    <MismatchSampleRows samples={result.mismatch_samples} />
                  </table>
                </div>
              </>
            ) : null}
          </div>
        ) : null}

        {phase === 'error' ? (
          <div className="validation-result validation-result-error">
            <p className="validation-status-title">Something went wrong</p>
            <p className="validation-error-detail">{errorMessage}</p>
          </div>
        ) : null}
      </div>
    </div>
  )
}