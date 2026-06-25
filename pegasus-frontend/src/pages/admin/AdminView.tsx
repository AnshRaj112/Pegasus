import React, { useCallback, useEffect, useState } from 'react';
import { Spin } from 'antd';
import { SafetyCertificateOutlined, AppstoreOutlined, ApiOutlined, LogoutOutlined, SettingOutlined } from '@ant-design/icons';
import { useAppDispatch } from '../../redux/store';
import { adminLogout, fetchAdminMe } from '../../shared/api/adminAuth';
import { authActions } from '../auth/Auth.reducer';
import { resetValidationOnLogout } from '../validation/resetValidationOnLogout';
import styles from './Admin.module.scss'; // ⚡ Import Module
import { Outlet, useNavigate, useLocation } from 'react-router-dom';

export const AdminView: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useAppDispatch();
  const [adminEmail, setAdminEmail] = useState<string | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  const refreshAdminSession = useCallback(async () => {
    setCheckingSession(true);
    try {
      const user = await fetchAdminMe();
      setAdminEmail(user.email);
    } catch {
      setAdminEmail(null);
    } finally {
      setCheckingSession(false);
    }
  }, []);

  useEffect(() => {
    void refreshAdminSession();
  }, [refreshAdminSession]);

  const handleAdminLogout = async () => {
    try {
      await adminLogout();
    } finally {
      setAdminEmail(null);
      resetValidationOnLogout(dispatch);
      dispatch(authActions.logoutSuccess());
    }
  };

  if (checkingSession) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 'calc(100vh - 64px)' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className={styles.adminLayout}>
      <aside className={styles.adminSidebar}>
        <div style={{ padding: '0 16px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <div style={{ width: '32px', height: '32px', backgroundColor: '#234B5F', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ffffff' }}>
              <SafetyCertificateOutlined style={{ fontSize: '20px' }} />
            </div>
            <span style={{ fontSize: '24px', fontWeight: 700, color: '#1b1b1c' }}>Admin Center</span>
          </div>
          <span style={{ fontSize: '14px', color: '#414755', fontWeight: 500, opacity: 0.7 }}>Technical Operations</span>
          <p style={{ fontSize: '12px', color: '#727786', margin: '8px 0 0', wordBreak: 'break-all' }}>{adminEmail}</p>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', flexGrow: 1 }}>
          <button
            onClick={() => navigate('/admin/workspace-management')}
            className={`${styles.navButton} ${location.pathname.includes('/workspace-management') ? styles.navButtonActive : ''}`}
          >
            <AppstoreOutlined style={{ fontSize: '18px' }} />
            Workspace Management
          </button>

          <button
            onClick={() => navigate('/admin/configure-store')}
            className={`${styles.navButton} ${location.pathname.includes('/configure-store') ? styles.navButtonActive : ''}`}
          >
            <ApiOutlined style={{ fontSize: '18px' }} />
            Configure Store
          </button>

          <button
            onClick={() => navigate('/admin/settings')}
            className={`${styles.navButton} ${location.pathname.includes('/settings') ? styles.navButtonActive : ''}`}
          >
            <SettingOutlined style={{ fontSize: '18px' }} />
            Configure Settings
          </button>
        </nav>

        <button
          type="button"
          onClick={() => void handleAdminLogout()}
          style={{ marginTop: 'auto', width: '100%', padding: '12px', backgroundColor: '#fff', border: '1px solid #d9d9d9', color: '#414755', fontSize: '14px', fontWeight: 500, borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', cursor: 'pointer' }}
        >
          <LogoutOutlined style={{ fontSize: '18px' }} />
          Admin sign out
        </button>
      </aside>

      <main className={styles.mainPanel}>
        <div className={styles.contentMaxWidth}>
          <Outlet />
        </div>
      </main>
    </div>
  );
};