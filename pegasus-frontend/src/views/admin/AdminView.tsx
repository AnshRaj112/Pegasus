import React, { useState } from 'react';
// import './ValidationWizardView.css'; 
import { ConfigureStoreSubView } from './sections/ConfigureStoreSubView';
import { WorkspaceMgmtSubView } from './sections/WorkspaceMgmtSubView'; // Connected Real Component!

export const AdminView: React.FC = () => {
  // Set default fallback view to mount the workspace tracker grid cleanly on load
  const [activeSubSection, setActiveSubSection] = useState<'store' | 'workspace'>('workspace');

  return (
    <div className="adminLayoutContainer">
      {/* Structural Navigator Left Administrative Sidebar */}
      <aside className="adminSidebar">
        <div style={{ marginBottom: 'var(--lg)', padding: '0 var(--xs)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sm)', marginBottom: 'var(--xs)' }}>
            <div style={{ width: '32px', height: '32px', background: 'var(--primary)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1", fontSize: '20px' }}>shield_person</span>
            </div>
            <span style={{ fontFamily: 'var(--font-h3)', fontSize: '18px', fontWeight: 'bold', color: 'var(--on-surface)' }}>Admin Center</span>
          </div>
          <span style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)', fontWeight: 500 }}>Technical Operations</span>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', flexGrow: 1 }}>
          <button 
            type="button"
            onClick={() => setActiveSubSection('workspace')} 
            className={`adminNavButton ${activeSubSection === 'workspace' ? 'adminNavButtonActive' : ''}`}
          >
            <span className="material-symbols-outlined">domain</span>
            Workspace Management
          </button>
          <button 
            type="button"
            onClick={() => setActiveSubSection('store')} 
            className={`adminNavButton ${activeSubSection === 'store' ? 'adminNavButtonActive' : ''}`}
          >
            <span className="material-symbols-outlined">settings_input_component</span>
            Configure Store
          </button>
        </nav>
        
        <button type="button" style={{ marginTop: 'auto', width: '100%', padding: 'var(--md)', background: 'var(--primary)', color: 'var(--on-primary)', fontWeight: 600, borderRadius: '8px', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 'var(--sm)', cursor: 'pointer' }}>
          <span className="material-symbols-outlined">add_circle</span>
          New Configuration
        </button>
      </aside>

      {/* Main Inner Sub-View Content Workspace Panel Canvas Content */}
      <main className="adminMainPanelWorkspace">
        {activeSubSection === 'store' ? <ConfigureStoreSubView /> : <WorkspaceMgmtSubView />}
      </main>
    </div>
  );
};

export default AdminView;
