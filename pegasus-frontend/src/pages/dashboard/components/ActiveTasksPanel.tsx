import React from 'react';

import { TaskItem } from '../Dashboard.interface';
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
        <h3 className={styles.panelTitle}>Active Tasks</h3>
        <span className={styles.panelMeta}>
          {isLoading ? 'Loading…' : `${tasks.length} jobs`}
        </span>
      </div>
      <div className={`${styles.panelTableContainer} custom-scrollbar`}>
        <table className={styles.taskTable}>
          <thead className={styles.tableHeaderSticky}>
            <tr>
              <th className={styles.tableHeadCell}>Task Name</th>
              <th className={styles.tableHeadCell}>Status</th>
              <th className={styles.tableHeadCell}>Progress</th>
            </tr>
          </thead>
          <tbody className={styles['zebra-table']}>
            {!isLoading && tasks.length === 0 && (
              <tr>
                <td colSpan={3} className={styles.tableEmptyCell}>
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
