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
        <h3 className={styles.customizerTitle}>Entity Customizer</h3>
        <p className={styles.customizerSubtitle}>
          Tailor your data view for specific reporting entities.
        </p>
      </div>

      <div className={styles.inputIconWrapper}>
        <Search size={16} className={styles.searchIcon} />
        <input
          type="text"
          placeholder="Search entities..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={styles.textInput}
        />
      </div>

      <div className={styles.fieldGroup}>
        <label className={styles.fieldLabel}>Entity Selector</label>
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
          <ChevronDown size={16} className={styles.selectDropdownIcon} />
        </div>
      </div>

      <div className={styles.toggleRow}>
        <div>
          <div className={styles.toggleTitle}>Incremental Tracking</div>
          <div className={styles.toggleHint}>Daily sync enabled</div>
        </div>
        <label className={styles.toggleContainer}>
          <input
            type="checkbox"
            checked={incrementalTracking}
            onChange={(e) => setIncrementalTracking(e.target.checked)}
            className={styles.toggleInput}
          />
          <div className={`${styles.toggleTrack} ${incrementalTracking ? styles.toggleTrackActive : ''}`}>
            <div className={`${styles.toggleThumb} ${incrementalTracking ? styles.toggleThumbActive : ''}`} />
          </div>
        </label>
      </div>

      {message && (
        <p className={styles.statusMessage}>{message}</p>
      )}

      <div className={styles.customizerFooterSpacer}>
        <button type="button" className={styles.submitActionBtn} onClick={handleCreate} disabled={saving}>
          <SlidersHorizontal size={16} />
          <span className={styles.btnLabelSpaced}>{saving ? 'Saving…' : 'Create Micro-Dashboard'}</span>
        </button>
      </div>
    </div>
  );
};
