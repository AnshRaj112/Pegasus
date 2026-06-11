import React from 'react';

import { type TaskItem } from '../Dashboard.interface';
import { TaskRow } from './TaskRow';
import styles from '../Dashboard.module.scss';

interface ActiveTasksPanelProps {
  tasks: TaskItem[];
  isLoading?: boolean;
}

export const ActiveTasksPanel: React.FC<ActiveTasksPanelProps> = ({ tasks, isLoading }) => {
  return (
    <div className={styles.panelCard}>
      <div className={styles.panelHeader}>
        <h3 style={{ fontSize: 'var(--label-md)', fontWeight: 500, margin: 0 }}>Active Tasks</h3>
        <span style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>
          {isLoading ? 'Loading…' : `${tasks.length} jobs`}
        </span>
      </div>
      <div className={`${styles.panelTableContainer} custom-scrollbar`}>
        <table className={styles.taskTable}>
          <thead className={styles.tableHeaderSticky}>
            <tr>
              <th style={{ padding: 'var(--md)', color: 'var(--on-surface-variant)', borderBottom: '1px solid var(--surface-variant)', fontSize: 'var(--label-md)' }}>Task Name</th>
              <th style={{ padding: 'var(--md)', color: 'var(--on-surface-variant)', borderBottom: '1px solid var(--surface-variant)', fontSize: 'var(--label-md)' }}>Status</th>
              <th style={{ padding: 'var(--md)', color: 'var(--on-surface-variant)', borderBottom: '1px solid var(--surface-variant)', fontSize: 'var(--label-md)' }}>Progress</th>
            </tr>
          </thead>
          <tbody className={styles['zebra-table']}>
            {!isLoading && tasks.length === 0 && (
              <tr>
                <td colSpan={3} style={{ padding: 'var(--md)', color: 'var(--on-surface-variant)', fontSize: 'var(--body-sm)' }}>
                  No validation jobs in queue.
                </td>
              </tr>
            )}
            {tasks.map((task) => <TaskRow key={task.id} task={task} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
};