import React from 'react';
import { CheckCircle2, Loader2, Calendar, AlertCircle } from 'lucide-react';
import { TaskItem } from '../Dashboard.interface'; // ⚡ We import it here now!

interface TaskRowProps {
  task: TaskItem;
}

export const TaskRow: React.FC<TaskRowProps> = ({ task }) => {
  const getStatusBadge = (status: TaskItem['status']) => {

    // Upgraded base style block: Removed background color panel bounds and outline borders
    const textOnlyBadgeStyle: React.CSSProperties = {
      fontSize: 'var(--body-sm)',
      fontWeight: 600,
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px'
    };

    switch (status) {
      case 'Completed':
        return (
          <span style={{ ...textOnlyBadgeStyle, color: '#166534' }}>
            <CheckCircle2 size={14} /> Completed
          </span>
        );
      case 'Running':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--xs)', color: '#ea580c', fontWeight: 600, fontSize: 'var(--body-sm)' }}>
            <Loader2 size={14} className="icon-spin-loop" /> Running
          </div>
        );
      case 'Scheduled':
        return (
          <span style={{ ...textOnlyBadgeStyle, color: 'var(--on-surface-variant)' }}>
            <Calendar size={14} /> Scheduled
          </span>
        );
      case 'Failed':
        return (
          <span style={{ ...textOnlyBadgeStyle, color: 'var(--error)' }}>
            <AlertCircle size={14} /> Failed
          </span>
        );
    }
  };

  const getProgressColor = (status: TaskItem['status']) => {
    if (status === 'Failed') return 'var(--error)';
    if (status === 'Completed') return '#16a34a';
    if (status === 'Scheduled') return 'var(--surface-dim)';
    return 'var(--primary)';
  };

  return (
    <tr style={{ borderBottom: '1px solid var(--surface-variant)' }}>
      <td style={{ padding: 'var(--md)' }}>
        <div style={{ fontWeight: 500, color: 'var(--on-surface)' }}>{task.name}</div>
        <div style={{ fontFamily: 'var(--font-body-sm)', fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>{task.time}</div>
      </td>
      <td style={{ padding: 'var(--md)' }}>{getStatusBadge(task.status)}</td>
      <td style={{ padding: 'var(--md)' }}>
        <div style={{ width: '100%', background: 'var(--surface-container)', borderRadius: '9999px', height: '6px', overflow: 'hidden' }}>
          <div style={{ backgroundColor: getProgressColor(task.status), height: '6px', borderRadius: '9999px', width: `${task.progress}%` }}></div>
        </div>
        {task.status === 'Running' && (
          <div style={{ fontSize: '10px', marginTop: 'var(--xs)', color: 'var(--on-surface-variant)' }}>{task.progress}% Processing</div>
        )}
      </td>
    </tr>
  );
};
