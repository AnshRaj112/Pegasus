import React, { useEffect } from 'react';
import { SearchOutlined } from '@ant-design/icons';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { reportActions } from './Report.reducer';
import { type TabType } from './Report.interface';
import { Active } from './step/Active';
import { Completed } from './step/Completed';
import { Saved } from './step/Saved';

export const Report: React.FC = () => {
  const dispatch = useAppDispatch();
  const { activeTab, searchQuery } = useAppSelector((s) => s.report);

  useEffect(() => {
    dispatch(reportActions.fetchReportsRequest());
  }, [dispatch]);

  useEffect(() => {
    if (activeTab !== 'Active') return;
    const timer = setInterval(() => dispatch(reportActions.fetchReportsRequest()), 5000);
    return () => clearInterval(timer);
  }, [activeTab, dispatch]);

  // Dynamic component rendering based on tab
  const renderStep = () => {
    switch (activeTab) {
      case 'Active': return <Active />;
      case 'Completed': return <Completed />;
      case 'Saved': return <Saved />;
      default: return <Active />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', maxWidth: '1440px', margin: '0 auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 600, color: '#1b1b1c', margin: '0 0 8px 0' }}>Validation Reports</h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: '14px' }}>Manage and monitor your data validation tests.</p>
      </div>

      <div style={{ backgroundColor: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)', overflow: 'hidden' }}>
        
        {/* Navigation & Search Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f1f5f9', padding: '0 24px', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '24px' }}>
            {(['Active', 'Completed', 'Saved'] as TabType[]).map((tab) => (
              <button
                key={tab}
                onClick={() => dispatch(reportActions.setTab(tab))}
                style={{
                  background: 'none',
                  border: 'none',
                  borderBottom: activeTab === tab ? '3px solid var(--primary)' : '3px solid transparent',
                  padding: '16px 0',
                  color: activeTab === tab ? '#1e293b' : '#64748b',
                  fontWeight: activeTab === tab ? 600 : 500,
                  fontSize: '14px',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                {tab}
              </button>
            ))}
          </div>

          <div style={{ position: 'relative', width: '100%', maxWidth: '320px', padding: '8px 0' }}>
            <input
              type="text"
              placeholder="Search by Test or Group Name"
              value={searchQuery}
              onChange={(e) => dispatch(reportActions.setSearchQuery(e.target.value))}
              style={{ width: '100%', padding: '8px 36px 8px 12px', borderRadius: '6px', border: '1px solid #d9d9d9', fontSize: '13px', color: '#1b1b1c', boxSizing: 'border-box', outline: 'none' }}
            />
            <SearchOutlined style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
          </div>
        </div>

        {/* Dynamic Step Content */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {renderStep()}
        </div>
      </div>
    </div>
  );
};