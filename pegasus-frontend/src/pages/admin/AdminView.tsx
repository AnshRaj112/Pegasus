import React from 'react';
import { SafetyCertificateOutlined, AppstoreOutlined, ApiOutlined, PlusCircleOutlined } from '@ant-design/icons';
import { useAppSelector, useAppDispatch } from '../../redux/store';
import { adminActions } from './Admin.reducer';

import { ConfigureStoreSubView } from './sections/ConfigureStoreSubView';
import { WorkspaceMgmtSubView } from './sections/WorkspaceMgmtSubView';
import styles from './Admin.module.scss'; // ⚡ Import Module

export const AdminView: React.FC = () => {
  const dispatch = useAppDispatch();
  const activeSubSection = useAppSelector((state) => state.admin.activeSubSection);

  return (
    <div className={styles.adminLayout}>
      <aside className={styles.adminSidebar}>
        <div style={{ padding: '0 16px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: '#0057c2', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
              <SafetyCertificateOutlined style={{ fontSize: '20px' }} />
            </div>
            <span style={{ fontSize: '24px', fontWeight: 700, color: '#1b1b1c' }}>Admin Center</span>
          </div>
          <span style={{ fontSize: '14px', color: '#414755', fontWeight: 500, opacity: 0.7 }}>Technical Operations</span>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', flexGrow: 1 }}>
          <button 
            onClick={() => dispatch(adminActions.setSubSection('workspace'))} 
            className={`${styles.navButton} ${activeSubSection === 'workspace' ? styles.navButtonActive : ''}`}
          >
            <AppstoreOutlined style={{ fontSize: '18px' }} />
            Workspace Management
          </button>
          
          <button 
            onClick={() => dispatch(adminActions.setSubSection('store'))} 
            className={`${styles.navButton} ${activeSubSection === 'store' ? styles.navButtonActive : ''}`}
          >
            <ApiOutlined style={{ fontSize: '18px' }} />
            Configure Store
          </button>
        </nav>
        
        <button style={{ marginTop: 'auto', width: '100%', padding: '12px', backgroundColor: '#e5e2e1', border: '1px solid #c1c6d7', color: '#1b1b1c', fontSize: '14px', fontWeight: 500, borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', cursor: 'pointer' }}>
          <PlusCircleOutlined style={{ fontSize: '18px' }} />
          New Configuration
        </button>
      </aside>

      <main className={styles.mainPanel}>
        <div className={styles.contentMaxWidth}>
          {activeSubSection === 'store' ? <ConfigureStoreSubView /> : <WorkspaceMgmtSubView />}
        </div>
      </main>
    </div>
  );
};