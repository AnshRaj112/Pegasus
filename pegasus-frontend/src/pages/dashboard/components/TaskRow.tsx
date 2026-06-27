import React from 'react';
import { CheckCircle2, Loader2, Calendar, AlertCircle } from 'lucide-react';
import { TaskItem } from '../Dashboard.interface';
import styles from './TaskRow.module.scss';

interface TaskRowProps {
  task: TaskItem;
}

const progressClass = (status: TaskItem['status']) => {
  if (status === 'Failed') return styles.progressFailed;
  if (status === 'Completed') return styles.progressCompleted;
  if (status === 'Scheduled') return styles.progressScheduled;
  return styles.progressDefault;
};

export const TaskRow: React.FC<TaskRowProps> = ({ task }) => {
  const getStatusBadge = (status: TaskItem['status']) => {
    switch (status) {
      case 'Completed':
        return (
          <span className={`${styles.badge} ${styles.badgeCompleted}`}>
            <CheckCircle2 size={14} /> Completed
          </span>
        );
      case 'Running':
        return (
          <div className={styles.badgeRunning}>
            <Loader2 size={14} className="icon-spin-loop" /> Running
          </div>
        );
      case 'Scheduled':
        return (
          <span className={`${styles.badge} ${styles.badgeScheduled}`}>
            <Calendar size={14} /> Scheduled
          </span>
        );
      case 'Failed':
        return (
          <span className={`${styles.badge} ${styles.badgeFailed}`}>
            <AlertCircle size={14} /> Failed
          </span>
        );
    }
  };

  return (
    <tr className={styles.row}>
      <td className={styles.cell}>
        <div className={styles.taskName}>{task.name}</div>
        <div className={styles.taskTime}>{task.time}</div>
      </td>
      <td className={styles.cell}>{getStatusBadge(task.status)}</td>
      <td className={styles.cell}>
        <div className={styles.progressTrack}>
          <div
            className={`${styles.progressFill} ${progressClass(task.status)}`}
            style={{ width: `${task.progress}%` }}
          />
        </div>
        {task.status === 'Running' && (
          <div className={styles.progressLabel}>{task.progress}% Processing</div>
        )}
      </td>
    </tr>
  );
};
