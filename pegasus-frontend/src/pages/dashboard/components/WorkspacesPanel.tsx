import React from 'react';
import { Lock, FolderHeart } from 'lucide-react';

import type { EntityInsight } from '../../../shared/api/Api';
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
        <h3 style={{ fontSize: 'var(--label-md)', fontWeight: 500, margin: 0 }}>Workspaces</h3>
        <span style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>
          {isLoading ? 'Loading…' : `${entities.length} entities`}
        </span>
      </div>

      <div className={`${styles.workspaceScrollContainer} custom-scrollbar`}>
        <div
          className={styles.defaultWorkspaceCard}
          style={{ border: '1px solid var(--surface-variant)', borderRadius: '8px', padding: 'var(--md)' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--xs)' }}>
              <Lock size={16} style={{ color: 'var(--on-surface-variant)' }} />
              <span style={{ fontWeight: 500, marginLeft: '4px' }}>Global Workspace</span>
            </div>
            <span className={styles['badge-system-highlight']}>System Default</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--xs)', fontSize: 'var(--body-sm)', marginTop: 'var(--sm)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--on-surface-variant)' }}>Total Entities:</span>
              <strong>{entities.length}</strong>
            </div>
          </div>
        </div>

        {entities.length === 0 && !isLoading && (
          <p style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)', padding: '8px 0' }}>
            No entity insights yet. Run validations to infer entities from filenames.
          </p>
        )}

        {entities.slice(0, 8).map((entity) => (
          <div
            key={entity.inferred_entity}
            className={styles.defaultWorkspaceCard}
            style={{ border: '1px solid var(--surface-variant)', borderRadius: '8px', padding: 'var(--md)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--xs)' }}>
              <FolderHeart size={16} style={{ color: 'var(--on-surface-variant)' }} />
              <span style={{ fontWeight: 500, marginLeft: '4px' }}>{entity.display_name}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--xs)', fontSize: 'var(--body-sm)', marginTop: 'var(--sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--on-surface-variant)' }}>Runs:</span>
                <strong>{entity.total_count}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--on-surface-variant)' }}>Pass rate:</span>
                <strong style={{ color: passRate(entity) >= 80 ? '#16a34a' : '#ea580c' }}>
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
