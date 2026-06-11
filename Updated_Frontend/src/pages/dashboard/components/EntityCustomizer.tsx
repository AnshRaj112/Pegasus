import React, { useState } from 'react';
import { Search, SlidersHorizontal, ChevronDown } from 'lucide-react';
import styles from '../Dashboard.module.scss'; // Reusing the parent styles for now

export const EntityCustomizer: React.FC = () => {
  const [incrementalTracking, setIncrementalTracking] = useState<boolean>(true);
  const [selectedEntity, setSelectedEntity] = useState<string>('Financial Records');

  return (
    <div className={styles.customizerCard}>
      <div>
        <h3 style={{ fontSize: 'var(--h3)', fontWeight: 600, margin: 0, color: 'var(--on-surface)' }}>Entity Customizer</h3>
        <p style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)', margin: '4px 0 0' }}>Tailor your data view for specific reporting entities.</p>
      </div>
      
      <div className={styles.inputIconWrapper}>
        <Search size={16} className={styles.searchIcon} style={{ left: '12px' }} />
        <input type="text" placeholder="Search entities..." className={styles.textInput} style={{ paddingLeft: '36px' }} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--xs)' }}>
        <label style={{ fontWeight: 500, fontSize: 'var(--label-md)' }}>Entity Selector</label>
        <div className={styles.inputIconWrapper}>
          <select 
            value={selectedEntity} 
            onChange={(e) => setSelectedEntity(e.target.value)}
            className={styles.selectInput}
          >
            <option>Financial Records</option>
            <option>User Telemetry</option>
            <option>Supply Chain Logs</option>
            <option>HR Master Data</option>
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
          <input type="checkbox" checked={incrementalTracking} onChange={(e) => setIncrementalTracking(e.target.checked)} style={{ display: 'none' }} />
          <div className={`${styles.toggleTrack} ${incrementalTracking ? styles.toggleTrackActive : ''}`}>
            <div className={`${styles.toggleThumb} ${incrementalTracking ? styles.toggleThumbActive : ''}`} />
          </div>
        </label>
      </div>

      <div className={styles.customizerFooterSpacer}>
        <button type="button" className={styles.submitActionBtn}>
          <SlidersHorizontal size={16} />
          <span style={{ marginLeft: '6px' }}>Create Micro-Dashboard</span>
        </button>
      </div>
    </div>
  );
};