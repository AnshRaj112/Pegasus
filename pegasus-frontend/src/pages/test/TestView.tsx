import { useEffect, useState } from 'react';
import { Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';

import { useAppDispatch } from '~/redux/store';

import ActiveView from './components/ActiveView';
import CompletedView from './components/Completed';
import SavedView from './components/SavedView';
import { testActions } from './Test.reducer';
import styles from './Test.module.scss';

type TabKeys = 'ACTIVE' | 'COMPLETED' | 'SAVED';

const TestView = () => {
  const dispatch = useAppDispatch();
  const [activeTab, setActiveTab] = useState<TabKeys>('ACTIVE');

  useEffect(() => {
    // Initial fetch based on default tab
    dispatch(testActions.fetchActiveTestsRequest());
  }, [dispatch]);

  const handleTabChange = (tab: TabKeys) => {
    setActiveTab(tab);
    // Lazy load the data when the tab is clicked
    if (tab === 'ACTIVE') dispatch(testActions.fetchActiveTestsRequest());
    if (tab === 'COMPLETED') dispatch(testActions.fetchCompletedTestsRequest());
    if (tab === 'SAVED') dispatch(testActions.fetchSavedTestsRequest());
  };

  const renderActiveComponent = () => {
    switch (activeTab) {
      case 'ACTIVE':
        return <ActiveView />;
      case 'COMPLETED':
        return <CompletedView />;
      case 'SAVED':
        return <SavedView />;
      default:
        return <ActiveView />;
    }
  };

  return (
    <div className={`w-100 ${styles.testContainer}`}>
      <div className="px-4 pt-4">
        <div className="d-flex justify-content-between align-items-end mb-3">
          <h1 className={styles.headerTitle}>Tests</h1>
          <Input 
            className={styles.searchInput}
            placeholder="Search by Test or Group Name" 
            prefix={<SearchOutlined />} 
            data-testid="tests-search-input"
          />
        </div>

        <div className={`d-flex ${styles.tabs}`}>
          <button 
            className={`${styles.tabBtn} ${activeTab === 'ACTIVE' ? styles['tabBtn--active'] : ''}`}
            onClick={() => handleTabChange('ACTIVE')}
            data-testid="tab-active"
          >
            Active
          </button>
          <button 
            className={`${styles.tabBtn} ${activeTab === 'COMPLETED' ? styles['tabBtn--active'] : ''}`}
            onClick={() => handleTabChange('COMPLETED')}
            data-testid="tab-completed"
          >
            Completed
          </button>
          <button 
            className={`${styles.tabBtn} ${activeTab === 'SAVED' ? styles['tabBtn--active'] : ''}`}
            onClick={() => handleTabChange('SAVED')}
            data-testid="tab-saved"
          >
            Saved
          </button>
        </div>
      </div>

      <div className="mt-2">
        {renderActiveComponent()}
      </div>
    </div>
  );
};

export default TestView;