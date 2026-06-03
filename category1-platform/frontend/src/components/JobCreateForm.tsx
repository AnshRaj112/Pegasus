import { useState, useEffect, useCallback } from 'react';
import { getDefaults, createJobWithUpload, type Defaults } from '../api/client';

interface Props {
  onJobCreated: (jobId: string) => void;
}

export default function JobCreateForm({ onJobCreated }: Props) {
  const [defaults, setDefaults] = useState<Defaults | null>(null);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [targetFile, setTargetFile] = useState<File | null>(null);
  const [keyColumns, setKeyColumns] = useState('');
  const [fileFormat, setFileFormat] = useState('csv');
  const [chunkSize, setChunkSize] = useState(10000);
  const [numPartitions, setNumPartitions] = useState(4096);
  const [memoryLimit, setMemoryLimit] = useState(1024);
  const [keyStrategy, setKeyStrategy] = useState('primary');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getDefaults().then(setDefaults).catch(console.error);
  }, []);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceFile || !targetFile || !keyColumns.trim()) {
      setError('Source file, target file, and key columns are required.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('source_file', sourceFile);
      formData.append('target_file', targetFile);
      formData.append('key_columns', keyColumns);
      formData.append('file_format', fileFormat);
      formData.append('chunk_size', String(chunkSize));
      formData.append('num_partitions', String(numPartitions));
      formData.append('memory_limit_mb', String(memoryLimit));
      formData.append('key_strategy', keyStrategy);
      const summary = await createJobWithUpload(formData);
      onJobCreated(summary.job_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create job');
    } finally {
      setSubmitting(false);
    }
  }, [sourceFile, targetFile, keyColumns, fileFormat, chunkSize, numPartitions, memoryLimit, keyStrategy, onJobCreated]);

  return (
    <form onSubmit={handleSubmit}>
      <div className="card">
        <h2>Data Sources</h2>
        <div className="form-grid">
          <div className="form-group">
            <label>Source File</label>
            <div className="file-upload" onClick={() => document.getElementById('source-input')?.click()}>
              <input id="source-input" type="file" accept=".csv,.tsv,.psv,.parquet,.orc,.avro,.xlsx,.xls" onChange={e => setSourceFile(e.target.files?.[0] || null)} />
              {sourceFile ? sourceFile.name : 'Click to select source file'}
            </div>
          </div>
          <div className="form-group">
            <label>Target File</label>
            <div className="file-upload" onClick={() => document.getElementById('target-input')?.click()}>
              <input id="target-input" type="file" accept=".csv,.tsv,.psv,.parquet,.orc,.avro,.xlsx,.xls" onChange={e => setTargetFile(e.target.files?.[0] || null)} />
              {targetFile ? targetFile.name : 'Click to select target file'}
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Reconciliation Configuration</h2>
        <div className="form-grid">
          <div className="form-group">
            <label>Key Columns (comma-separated)</label>
            <input value={keyColumns} onChange={e => setKeyColumns(e.target.value)} placeholder="e.g. employee_id" />
          </div>
          <div className="form-group">
            <label>Key Strategy</label>
            <select value={keyStrategy} onChange={e => setKeyStrategy(e.target.value)}>
              {(defaults?.key_strategies || ['primary']).map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>File Format</label>
            <select value={fileFormat} onChange={e => setFileFormat(e.target.value)}>
              {(defaults?.file_formats || ['csv']).map(f => (
                <option key={f} value={f}>{f.toUpperCase()}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Chunk Size</label>
            <select value={chunkSize} onChange={e => setChunkSize(Number(e.target.value))}>
              {(defaults?.chunk_sizes || [1000, 5000, 10000, 50000]).map(s => (
                <option key={s} value={s}>{s.toLocaleString()} rows</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Partitions</label>
            <select value={numPartitions} onChange={e => setNumPartitions(Number(e.target.value))}>
              {(defaults?.partition_counts || [1024, 2048, 4096, 8192]).map(p => (
                <option key={p} value={p}>{p.toLocaleString()}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Memory Limit (MB)</label>
            <input type="number" value={memoryLimit} onChange={e => setMemoryLimit(Number(e.target.value))} min={256} max={65536} />
          </div>
        </div>
      </div>

      {error && <div style={{ color: 'var(--error)', marginBottom: '1rem' }}>{error}</div>}

      <button type="submit" className="btn" disabled={submitting}>
        {submitting ? 'Starting Reconciliation...' : 'Start Reconciliation'}
      </button>
    </form>
  );
}
