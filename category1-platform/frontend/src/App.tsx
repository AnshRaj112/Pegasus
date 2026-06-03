import { useState } from 'react';
import JobCreateForm from './components/JobCreateForm';
import JobList from './components/JobList';
import JobDetail from './components/JobDetail';

type View = 'create' | 'jobs' | 'detail';

export default function App() {
  const [view, setView] = useState<View>('create');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const handleJobCreated = (jobId: string) => {
    setSelectedJobId(jobId);
    setView('detail');
  };

  const handleSelectJob = (jobId: string) => {
    setSelectedJobId(jobId);
    setView('detail');
  };

  return (
    <div className="app">
      <header className="header">
        <h1>
          Category-1 Reconciliation
          <span className="badge">Enterprise</span>
        </h1>
        <nav className="nav">
          <button className={view === 'create' ? 'active' : ''} onClick={() => setView('create')}>
            New Job
          </button>
          <button className={view === 'jobs' ? 'active' : ''} onClick={() => setView('jobs')}>
            Jobs
          </button>
        </nav>
      </header>

      <main className="main">
        {view === 'create' && <JobCreateForm onJobCreated={handleJobCreated} />}
        {view === 'jobs' && <JobList onSelectJob={handleSelectJob} />}
        {view === 'detail' && selectedJobId && (
          <JobDetail jobId={selectedJobId} onBack={() => setView('jobs')} />
        )}
      </main>
    </div>
  );
}
