import React, { useMemo, useState } from 'react';
import { Search, SlidersHorizontal, ChevronDown } from 'lucide-react';

import { type EntityInsight } from '../../../shared/api/Api';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { dashboardActions } from '../Dashboard.reducer';
import styles from '../Dashboard.module.scss';

interface EntityCustomizerProps {
  entities: EntityInsight[];
}

export const EntityCustomizer: React.FC<EntityCustomizerProps> = ({ entities }) => {
  const dispatch = useAppDispatch();
  const createEntityState = useAppSelector((state) => state.dashboard.createEntityState);

  const [incrementalTracking, setIncrementalTracking] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntity, setSelectedEntity] = useState('');

  const filtered = useMemo(
    () =>
      entities.filter((e) =>
        e.display_name.toLowerCase().includes(searchQuery.toLowerCase()),
      ),
    [entities, searchQuery],
  );

  const activeEntity = selectedEntity || filtered[0]?.display_name || '';
  const saving = createEntityState.isFetching;
  const message = createEntityState.data ?? createEntityState.error;

  const handleCreate = () => {
    const name = searchQuery.trim() || activeEntity;
    if (!name) return;
    dispatch(dashboardActions.createEntityRequest({ display_name: name }));
  };

  return (
    <div className={styles.customizerCard}>
      <div>
        <h3 style={{ fontSize: 'var(--h3)', fontWeight: 600, margin: 0, color: 'var(--on-surface)' }}>Entity Customizer</h3>
        <p style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)', margin: '4px 0 0' }}>
          Tailor your data view for specific reporting entities.
        </p>
      </div>

      <div className={styles.inputIconWrapper}>
        <Search size={16} className={styles.searchIcon} style={{ left: '12px' }} />
        <input
          type="text"
          placeholder="Search entities..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={styles.textInput}
          style={{ paddingLeft: '36px' }}
        />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--xs)' }}>
        <label style={{ fontWeight: 500, fontSize: 'var(--label-md)' }}>Entity Selector</label>
        <div className={styles.inputIconWrapper}>
          <select
            value={activeEntity}
            onChange={(e) => setSelectedEntity(e.target.value)}
            className={styles.selectInput}
          >
            {filtered.length === 0 && <option value="">No entities yet</option>}
            {filtered.map((e) => (
              <option key={e.inferred_entity} value={e.display_name}>
                {e.display_name} ({e.total_count} runs)
              </option>
            ))}
          </select>
          <ChevronDown size={16} className={styles.selectDropdownIcon} style={{ right: '12px' }} />
        </div>
      </div>

      <div className={styles.toggleRow}>
        <div>
          <div style={{ fontWeight: 500 }}>Incremental Tracking</div>
          <div style={{ fontSize: '10px', color: 'var(--on-surface-variant)' }}>Daily sync enabled</div>
        </div>
        <label className={styles.toggleContainer}>
          <input
            type="checkbox"
            checked={incrementalTracking}
            onChange={(e) => setIncrementalTracking(e.target.checked)}
            style={{ display: 'none' }}
          />
          <div className={`${styles.toggleTrack} ${incrementalTracking ? styles.toggleTrackActive : ''}`}>
            <div className={`${styles.toggleThumb} ${incrementalTracking ? styles.toggleThumbActive : ''}`} />
          </div>
        </label>
      </div>

      {message && (
        <p style={{ fontSize: '12px', color: 'var(--on-surface-variant)', margin: 0 }}>{message}</p>
      )}

      <div className={styles.customizerFooterSpacer}>
        <button type="button" className={styles.submitActionBtn} onClick={handleCreate} disabled={saving}>
          <SlidersHorizontal size={16} />
          <span style={{ marginLeft: '6px' }}>{saving ? 'Saving…' : 'Create Micro-Dashboard'}</span>
        </button>
      </div>
    </div>
  );
};
