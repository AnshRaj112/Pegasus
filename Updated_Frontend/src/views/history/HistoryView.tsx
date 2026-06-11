import React, { useState } from 'react';
import { ValidationHistoryTable } from './components/ValidationHistoryTable';
import { MappingHistoryTable } from './components/MappingHistoryTable';

export const HistoryView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'validation' | 'mapping'>('validation');
  const [searchQuery, setSearchQuery] = useState<string>('');

  return (
    <div className="historyLayoutContainer">
      {/* Upper Context Control Banner Area Header */}
      <div className="historyTopHeader">
        <div>
          <h1 style={{ fontFamily: 'var(--font-h1)', fontSize: 'var(--h1)', color: 'var(--on-surface)', margin: '0 0 var(--xs) 0', fontWeight: 600, letterSpacing: '-0.02em' }}>
            Execution History
          </h1>
          <p style={{ fontSize: 'var(--body-md)', color: 'var(--on-surface-variant)', margin: 0 }}>
            Review historical validation results and schema mapping logs.
          </p>
        </div>
        
        <div className="historyControlBlock">
          <div style={{ position: 'relative' }}>
            <span className="material-symbols-outlined" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--on-surface-variant)' }}>
              search
            </span>
            <input 
              type="text" 
              placeholder="Search logs..." 
              className="historySearchInput"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button type="button" style={{ height: '40px', padding: '0 var(--md)', background: 'var(--surface)', border: '1px solid var(--outline-variant)', borderRadius: '8px', color: 'var(--on-surface)', fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>filter_list</span> Filter
          </button>
        </div>
      </div>

      {/* Primary Tab Sheet Multi-View Data Envelope */}
      <div className="historyMasterCard">
        <div className="historyTabsBanner">
          <button 
            type="button"
            onClick={() => setActiveTab('validation')}
            className={`historyTabButton ${activeTab === 'validation' ? 'historyTabButtonActive' : ''}`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>analytics</span>
            Validation History
          </button>
          <button 
            type="button"
            onClick={() => setActiveTab('mapping')}
            className={`historyTabButton ${activeTab === 'mapping' ? 'historyTabButtonActive' : ''}`}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>schema</span>
            Mapping History
          </button>
        </div>

        {/* Tab Swapping Injection Matrix Window */}
        {activeTab === 'validation' ? <ValidationHistoryTable /> : <MappingHistoryTable />}
      </div>

      {/* Platform Level Shared Grid Virtual Pagination Controls */}
      <div className="historyPaginationRow">
        <span style={{ color: 'var(--on-surface-variant)' }}>
          Showing <strong>1 to 10</strong> of 2,451 records
        </span>
        <div className="paginationNavBox">
          <button type="button" className="paginationNumBtn"><span className="material-symbols-outlined" style={{ fontSize: '18px' }}>chevron_left</span></button>
          <button type="button" className="paginationNumBtn paginationNumBtnActive">1</button>
          <button type="button" className="paginationNumBtn">2</button>
          <button type="button" className="paginationNumBtn">3</button>
          <span style={{ padding: '0 var(--xs)', color: 'var(--on-surface-variant)' }}>...</span>
          <button type="button" className="paginationNumBtn">246</button>
          <button type="button" className="paginationNumBtn"><span className="material-symbols-outlined" style={{ fontSize: '18px' }}>chevron_right</span></button>
        </div>
      </div>
    </div>
  );
};
