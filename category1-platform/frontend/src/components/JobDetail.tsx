import { useState, useEffect, useCallback } from 'react';
import { getJob, getJobSummary, getReportUrl, type ReconciliationResult, type JobSummary } from '../api/client';

interface Props {
  jobId: string;
  onBack: () => void;
}

export default function JobDetail({ jobId, onBack }: Props) {
  const [result, setResult] = useState<ReconciliationResult | null>(null);
  const [summary, setSummary] = useState<JobSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const poll = useCallback(async () => {
    try {
      const [job, sum] = await Promise.all([
        getJob(jobId),
        getJobSummary(jobId),
      ]);
      setResult(job);
      setSummary(sum);
      setLoading(false);
      return job.status;
    } catch {
      setLoading(false);
      return 'failed';
    }
  }, [jobId]);

  useEffect(() => {
    poll();
    const interval = setInterval(async () => {
      const status = await poll();
      if (status === 'completed' || status === 'failed') {
        clearInterval(interval);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [poll]);

  if (loading && !result) {
    return <div className="empty-state">Loading job details...</div>;
  }

  if (!result) {
    return <div className="empty-state">Job not found.</div>;
  }

  const isRunning = !['completed', 'failed', 'cancelled'].includes(result.status);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <button className="btn btn-secondary" onClick={onBack} style={{ marginRight: '1rem' }}>Back</button>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Job: {jobId.slice(0, 8)}...</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span className={`status-badge ${isRunning ? 'running' : result.status}`}>{result.status}</span>
          {result.status === 'completed' && (
            <a href={getReportUrl(jobId)} target="_blank" rel="noreferrer" className="btn" style={{ textDecoration: 'none', fontSize: '0.8rem', padding: '0.4rem 1rem' }}>
              Download Report
            </a>
          )}
        </div>
      </div>

      {isRunning && summary && (
        <div className="card">
          <h2>Progress: {summary.current_phase}</h2>
          <div className="progress-bar">
            <div className="fill" style={{ width: `${summary.progress_pct}%` }} />
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {summary.progress_pct.toFixed(0)}% complete
          </div>
        </div>
      )}

      {result.error_message && (
        <div className="card" style={{ borderColor: 'var(--error)' }}>
          <h2 style={{ color: 'var(--error)' }}>Error</h2>
          <p>{result.error_message}</p>
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="value">{result.execution_stats?.source_rows_processed?.toLocaleString() ?? '-'}</div>
          <div className="label">Source Rows</div>
        </div>
        <div className="stat-card">
          <div className="value">{result.execution_stats?.target_rows_processed?.toLocaleString() ?? '-'}</div>
          <div className="label">Target Rows</div>
        </div>
        <div className="stat-card missing">
          <div className="value">{result.missing_count.toLocaleString()}</div>
          <div className="label">Missing</div>
        </div>
        <div className="stat-card extra">
          <div className="value">{result.extra_count.toLocaleString()}</div>
          <div className="label">Extra</div>
        </div>
        <div className="stat-card mismatch">
          <div className="value">{result.mismatched_count.toLocaleString()}</div>
          <div className="label">Mismatched</div>
        </div>
        <div className="stat-card match">
          <div className="value">{result.matching_count.toLocaleString()}</div>
          <div className="label">Matching</div>
        </div>
      </div>

      {result.schema_validation && !result.schema_validation.is_valid && (
        <div className="card">
          <h2>Schema Differences</h2>
          <table className="table">
            <thead>
              <tr><th>Column</th><th>Type</th><th>Source</th><th>Target</th></tr>
            </thead>
            <tbody>
              {result.schema_validation.differences.map((d, i) => (
                <tr key={i}>
                  <td>{d.column}</td>
                  <td>{d.difference_type}</td>
                  <td>{d.source_value || '-'}</td>
                  <td>{d.target_value || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result.sample_mismatches && result.sample_mismatches.length > 0 && (
        <div className="card">
          <h2>Sample Mismatches ({result.sample_mismatches.length})</h2>
          <table className="table">
            <thead>
              <tr><th>Type</th><th>Key</th><th>Partition</th><th>Column Differences</th></tr>
            </thead>
            <tbody>
              {result.sample_mismatches.slice(0, 50).map((m, i) => (
                <tr key={i}>
                  <td><span className={`status-badge ${m.mismatch_type === 'missing' ? 'failed' : m.mismatch_type === 'extra' ? 'running' : 'pending'}`}>{m.mismatch_type}</span></td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{m.record_key}</td>
                  <td>{m.partition_id}</td>
                  <td>
                    {m.column_differences?.map(cd => (
                      <div key={cd.column} style={{ fontSize: '0.8rem' }}>
                        <strong>{cd.column}:</strong> {cd.source_value ?? 'NULL'} → {cd.target_value ?? 'NULL'}
                      </div>
                    )) || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result.execution_stats && (
        <div className="card">
          <h2>Execution Statistics</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="value">{result.execution_stats.duration_seconds.toFixed(1)}s</div>
              <div className="label">Duration</div>
            </div>
            <div className="stat-card">
              <div className="value">{result.execution_stats.partitions_processed}</div>
              <div className="label">Partitions</div>
            </div>
            <div className="stat-card">
              <div className="value">{result.execution_stats.peak_memory_mb.toFixed(0)} MB</div>
              <div className="label">Peak Memory</div>
            </div>
            <div className="stat-card">
              <div className="value">{result.execution_stats.disk_spill_mb.toFixed(1)} MB</div>
              <div className="label">Disk Spill</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
