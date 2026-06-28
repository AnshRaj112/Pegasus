import React from 'react';
import { Lock, FolderHeart } from 'lucide-react';

import { EntityInsight } from '../../../shared/api/Api';
import styles from '../Dashboard.module.scss';

interface WorkspacesPanelProps {
  entities: EntityInsight[];
  isLoading?: boolean;
}

export const WorkspacesPanel: React.FC<WorkspacesPanelProps> = ({ entities, isLoading }) => {
  const passRate = (e: EntityInsight) =>
    e.total_count > 0 ? Math.round((e.success_count / e.total_count) * 100) : 0;

  return (
    <div className={styles.panelCard}>
      <div className={styles.panelHeader}>
        <h3 className={styles.panelTitle}>Workspaces</h3>
        <span className={styles.panelMeta}>
          {isLoading ? 'Loading…' : `${entities.length} entities`}
        </span>
      </div>

      <div className={`${styles.workspaceScrollContainer} custom-scrollbar`}>
        <div className={styles.defaultWorkspaceCard}>
          <div className={styles.workspaceCardHeader}>
            <div className={styles.workspaceTitleRow}>
              <Lock size={16} className={styles.workspaceIcon} />
              <span className={styles.workspaceTitle}>Global Workspace</span>
            </div>
            <span className={styles['badge-system-highlight']}>System Default</span>
          </div>
          <div className={styles.workspaceStats}>
            <div className={styles.workspaceStatRow}>
              <span className={styles.workspaceStatLabel}>Total Entities:</span>
              <strong>{entities.length}</strong>
            </div>
          </div>
        </div>

        {entities.length === 0 && !isLoading && (
          <p className={styles.workspaceEmptyHint}>
            No entity insights yet. Run validations to infer entities from filenames.
          </p>
        )}

        {entities.slice(0, 8).map((entity) => (
          <div key={entity.inferred_entity} className={styles.defaultWorkspaceCard}>
            <div className={styles.workspaceTitleRow}>
              <FolderHeart size={16} className={styles.workspaceIcon} />
              <span className={styles.workspaceTitle}>{entity.display_name}</span>
            </div>
            <div className={styles.workspaceStats}>
              <div className={styles.workspaceStatRow}>
                <span className={styles.workspaceStatLabel}>Runs:</span>
                <strong>{entity.total_count}</strong>
              </div>
              <div className={styles.workspaceStatRow}>
                <span className={styles.workspaceStatLabel}>Pass rate:</span>
                <strong className={passRate(entity) >= 80 ? styles.passRateHigh : styles.passRateLow}>
                  {passRate(entity)}%
                </strong>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
