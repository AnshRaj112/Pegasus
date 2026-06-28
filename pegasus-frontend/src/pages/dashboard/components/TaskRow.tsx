import React from 'react';
import { CheckCircle2, Loader2, Calendar, AlertCircle } from 'lucide-react';
import { TaskItem } from '../Dashboard.interface';
import styles from './TaskRow.module.scss';

interface TaskRowProps {
  task: TaskItem;
}

const progressMeterClass = (status: TaskItem['status']) => {
  if (status === 'Failed') return styles.progressMeterFailed;
  if (status === 'Completed') return styles.progressMeterCompleted;
  if (status === 'Scheduled') return styles.progressMeterScheduled;
  return '';
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
        <progress
          className={`${styles.progressMeter} ${progressMeterClass(task.status)}`}
          value={task.progress}
          max={100}
        />
        {task.status === 'Running' && (
          <div className={styles.progressLabel}>{task.progress}% Processing</div>
        )}
      </td>
    </tr>
  );
};
