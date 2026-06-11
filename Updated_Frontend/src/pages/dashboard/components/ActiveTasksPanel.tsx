import React from 'react';

import { type TaskItem } from '../Dashboard.interface';
import { TaskRow } from './TaskRow';
import styles from '../Dashboard.module.scss';

interface ActiveTasksPanelProps {
  tasks: TaskItem[];
}

export const ActiveTasksPanel: React.FC<ActiveTasksPanelProps> = ({ tasks }) => {
  return (
    <div className={styles.panelCard}>
      <div className={styles.panelHeader}>
        <h3 style={{ fontSize: 'var(--label-md)', fontWeight: 500, margin: 0 }}>Active Tasks</h3>
        <button type="button" className={styles.secondaryBtn}>View All</button>
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
            {tasks.map(task => <TaskRow key={task.id} task={task} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
};