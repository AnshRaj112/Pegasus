import React, { useEffect, useMemo } from 'react';
import { SearchOutlined, FilterOutlined, BarChartOutlined, NodeIndexOutlined, LeftOutlined, RightOutlined } from '@ant-design/icons';
import { useAppSelector, useAppDispatch } from '../../redux/store';
import { historyActions } from './History.reducer';

import { ValidationHistoryTable } from './components/ValidationHistoryTable';
import { MappingHistoryTable } from './components/MappingHistoryTable';
import styles from './History.module.scss';

const buildPageNumbers = (current: number, totalPages: number): (number | 'ellipsis')[] => {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const pages: (number | 'ellipsis')[] = [1];
  if (current > 3) pages.push('ellipsis');
  const start = Math.max(2, current - 1);
  const end = Math.min(totalPages - 1, current + 1);
  for (let p = start; p <= end; p += 1) pages.push(p);
  if (current < totalPages - 2) pages.push('ellipsis');
  pages.push(totalPages);
  return pages;
};

export const HistoryView: React.FC = () => {
  const dispatch = useAppDispatch();
  const activeTab = useAppSelector((state) => state.history.activeTab);
  const searchQuery = useAppSelector((state) => state.history.searchQuery);
  const pageSize = useAppSelector((state) => state.history.pageSize);
  const validationLogs = useAppSelector((state) => state.history.validationLogs);
  const mappingLogs = useAppSelector((state) => state.history.mappingLogs);

  const activeLogs = activeTab === 'validation' ? validationLogs : mappingLogs;
  const totalPages = Math.max(1, Math.ceil(activeLogs.total / pageSize));
  const pageNumbers = useMemo(() => buildPageNumbers(activeLogs.page, totalPages), [activeLogs.page, totalPages]);
  const rangeStart = activeLogs.total === 0 ? 0 : (activeLogs.page - 1) * pageSize + 1;
  const rangeEnd = Math.min(activeLogs.page * pageSize, activeLogs.total);

  useEffect(() => {
    dispatch(historyActions.fetchHistoryRequest({ tab: activeTab }));
  }, [dispatch, activeTab]);

  const goToPage = (page: number) => {
    if (page < 1 || page > totalPages || page === activeLogs.page) return;
    dispatch(historyActions.setPage({ tab: activeTab, page }));
  };

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
            {activeLogs.isFetching ? (
              'Loading...'
            ) : (
              <>
                Showing <strong>{rangeStart} to {rangeEnd}</strong> of {activeLogs.total.toLocaleString()} records
              </>
            )}
          </span>
          <div className={styles.paginationNavBox}>
            <button type="button" className={styles.paginationNumBtn} onClick={() => goToPage(activeLogs.page - 1)} disabled={activeLogs.page <= 1}>
              <LeftOutlined style={{ fontSize: '12px' }} />
            </button>
            {pageNumbers.map((page, idx) =>
              page === 'ellipsis' ? (
                <span key={`ellipsis-${idx}`} style={{ padding: '0 4px', color: '#414755' }}>...</span>
              ) : (
                <button
                  key={page}
                  type="button"
                  className={`${styles.paginationNumBtn} ${page === activeLogs.page ? styles.paginationNumBtnActive : ''}`}
                  onClick={() => goToPage(page)}
                >
                  {page}
                </button>
              ),
            )}
            <button type="button" className={styles.paginationNumBtn} onClick={() => goToPage(activeLogs.page + 1)} disabled={activeLogs.page >= totalPages}>
              <RightOutlined style={{ fontSize: '12px' }} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
