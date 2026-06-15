import React from 'react';
import { SearchOutlined, FilterOutlined, BarChartOutlined, NodeIndexOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import { useAppSelector, useAppDispatch } from '../../redux/store';
import { historyActions } from './History.reducer';

import { ValidationHistoryTable } from './components/ValidationHistoryTable';
import { MappingHistoryTable } from './components/MappingHistoryTable';
import styles from './History.module.scss';

export const HistoryView: React.FC = () => {
  const dispatch = useAppDispatch();
  const activeTab = useAppSelector((state) => state.history.activeTab);
  const searchQuery = useAppSelector((state) => state.history.searchQuery);

  return (
    <div className={styles.historyLayout}>
      <div className={styles.historyTopHeader}>
        <div>
          <h1 style={{ fontSize: '38px', color: '#1b1b1c', margin: '0 0 4px 0', fontWeight: 600, letterSpacing: '-0.02em' }}>
            Execution History
          </h1>
          <p style={{ fontSize: '14px', color: '#414755', margin: 0 }}>
            Review historical validation results and schema mapping logs.
          </p>
        </div>
        
        <div className={styles.historyControlBlock}>
          <div style={{ position: 'relative' }}>
            <SearchOutlined style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#727786', fontSize: '18px' }} />
            <input 
              type="text" 
              placeholder="Search logs..." 
              value={searchQuery}
              onChange={(e) => dispatch(historyActions.setSearchQuery(e.target.value))}
              style={{ padding: '0 16px 0 36px', height: '40px', boxSizing: 'border-box', border: '1px solid #d9d9d9', borderRadius: '8px', fontSize: '14px', outline: 'none' }}
            />
          </div>
          <button style={{ height: '40px', padding: '0 16px', background: '#ffffff', border: '1px solid #d9d9d9', borderRadius: '8px', color: '#1b1b1c', fontSize: '14px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <FilterOutlined style={{ fontSize: '18px' }} /> Filter
          </button>
        </div>
      </div>

      <div className={styles.historyMasterCard}>
        <div className={styles.historyTabsBanner}>
          <button 
            onClick={() => dispatch(historyActions.setActiveTab('validation'))}
            className={`${styles.historyTabButton} ${activeTab === 'validation' ? styles.historyTabButtonActive : ''}`}
          >
            <BarChartOutlined style={{ fontSize: '18px' }} />
            Validation History
          </button>
          <button 
            onClick={() => dispatch(historyActions.setActiveTab('mapping'))}
            className={`${styles.historyTabButton} ${activeTab === 'mapping' ? styles.historyTabButtonActive : ''}`}
          >
            <NodeIndexOutlined style={{ fontSize: '18px' }} />
            Mapping History
          </button>
        </div>

        {activeTab === 'validation' ? <ValidationHistoryTable /> : <MappingHistoryTable />}
        
        <div className={styles.historyPaginationRow}>
          <span style={{ color: '#414755', fontSize: '12px' }}>
            Showing <strong>1 to 10</strong> of 2,451 records
          </span>
          <div className={styles.paginationNavBox}>
            <button className={styles.paginationNumBtn}><LeftOutlined style={{ fontSize: '12px' }} /></button>
            <button className={`${styles.paginationNumBtn} ${styles.paginationNumBtnActive}`}>1</button>
            <button className={styles.paginationNumBtn}>2</button>
            <button className={styles.paginationNumBtn}>3</button>
            <span style={{ padding: '0 4px', color: '#414755' }}>...</span>
            <button className={styles.paginationNumBtn}>246</button>
            <button className={styles.paginationNumBtn}><RightOutlined style={{ fontSize: '12px' }} /></button>
          </div>
        </div>
      </div>
    </div>
  );
};