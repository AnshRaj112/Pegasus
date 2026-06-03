import { useState, useEffect, useCallback } from 'react';
import { listJobs, type JobSummary } from '../api/client';

interface Props {
  onSelectJob: (jobId: string) => void;
}

export default function JobList({ onSelectJob }: Props) {
  const [jobs, setJobs] = useState<JobSummary[]>([]);

  const refresh = useCallback(async () => {
    try {
      const data = await listJobs();
      setJobs(data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (jobs.length === 0) {
    return (
      <div className="empty-state">
        <p>No reconciliation jobs yet.</p>
        <p style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>Create a new job to get started.</p>
      </div>
    );
  }

  return (
    <div className="job-list">
      {jobs.map(job => (
        <div key={job.job_id} className="job-item" onClick={() => onSelectJob(job.job_id)}>
          <div>
            <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{job.job_id.slice(0, 8)}...</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              {new Date(job.created_at).toLocaleString()} — {job.current_phase || 'Pending'}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {!['completed', 'failed'].includes(job.status) && (
              <div style={{ width: 100 }}>
                <div className="progress-bar" style={{ height: 4 }}>
                  <div className="fill" style={{ width: `${job.progress_pct}%` }} />
                </div>
              </div>
            )}
            <span className={`status-badge ${job.status === 'completed' ? 'completed' : job.status === 'failed' ? 'failed' : 'running'}`}>
              {job.status}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
