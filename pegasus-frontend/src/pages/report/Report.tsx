import React, { useEffect } from 'react';
import { SearchOutlined } from '@ant-design/icons';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { reportActions } from './Report.reducer';
import { TabType } from './Report.interface';
import { Active } from './step/Active';
import { Completed } from './step/Completed';
import { Saved } from './step/Saved';
import styles from './Report.module.scss';

const Report: React.FC = () => {
  const dispatch = useAppDispatch();
  const { activeTab, searchQuery, activeReports } = useAppSelector((s) => s.report);
  const activeReportCount = activeReports.data.length;

  useEffect(() => {
    dispatch(reportActions.fetchReportsRequest());
  }, [dispatch]);

  useEffect(() => {
    if (activeTab !== 'Active') return;
    if (activeReportCount === 0) return;
    const timer = setInterval(() => dispatch(reportActions.fetchReportsRequest()), 5000);
    return () => clearInterval(timer);
  }, [activeTab, activeReportCount, dispatch]);

  const renderStep = () => {
    switch (activeTab) {
      case 'Active': return <Active />;
      case 'Completed': return <Completed />;
      case 'Saved': return <Saved />;
      default: return <Active />;
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Validation Reports</h1>
        <p className={styles.subtitle}>Manage and monitor your data validation tests.</p>
      </div>

      <div className={styles.card}>
        <div className={styles.toolbar}>
          <div className={styles.tabs}>
            {(['Active', 'Completed', 'Saved'] as TabType[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => dispatch(reportActions.setTab(tab))}
                className={`${styles.tabBtn} ${activeTab === tab ? styles.tabBtnActive : ''}`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className={styles.searchWrap}>
            <input
              type="text"
              placeholder="Search by Test or Group Name"
              value={searchQuery}
              onChange={(e) => dispatch(reportActions.setSearchQuery(e.target.value))}
              className={styles.searchInput}
            />
            <SearchOutlined className={styles.searchIcon} />
          </div>
        </div>

        <div className={styles.content}>
          {renderStep()}
        </div>
      </div>
    </div>
  );
};

export default Report;
