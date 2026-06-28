import React, { useCallback, useEffect, useState } from 'react';
import { Spin } from 'antd';
import { SafetyCertificateOutlined, AppstoreOutlined, ApiOutlined, LogoutOutlined, SettingOutlined } from '@ant-design/icons';
import { useAppDispatch } from '../../redux/store';
import { adminLogout, fetchAdminMe } from '../../shared/api/adminAuth';
import { authActions } from '../auth/Auth.reducer';
import { resetValidationOnLogout } from '../validation/resetValidationOnLogout';
import styles from './Admin.module.scss';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';

const AdminView: React.FC = () => {
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
      <div className={styles.sessionLoading}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className={styles.adminLayout}>
      <aside className={styles.adminSidebar}>
        <div className={styles.sidebarBrand}>
          <div className={styles.sidebarBrandRow}>
            <div className={styles.sidebarLogo}>
              <SafetyCertificateOutlined className={styles.sidebarLogoIcon} />
            </div>
            <span className={styles.sidebarTitle}>Admin Center</span>
          </div>
          <span className={styles.sidebarSubtitle}>Technical Operations</span>
          <p className={styles.sidebarEmail}>{adminEmail}</p>
        </div>

        <nav className={styles.sidebarNav}>
          <button
            type="button"
            onClick={() => navigate('/admin/workspace-management')}
            className={`${styles.navButton} ${location.pathname.includes('/workspace-management') ? styles.navButtonActive : ''}`}
          >
            <AppstoreOutlined className={styles.navIcon} />
            Workspace Management
          </button>

          <button
            type="button"
            onClick={() => navigate('/admin/configure-store')}
            className={`${styles.navButton} ${location.pathname.includes('/configure-store') ? styles.navButtonActive : ''}`}
          >
            <ApiOutlined className={styles.navIcon} />
            Configure Store
          </button>

          <button
            type="button"
            onClick={() => navigate('/admin/settings')}
            className={`${styles.navButton} ${location.pathname.includes('/settings') ? styles.navButtonActive : ''}`}
          >
            <SettingOutlined className={styles.navIcon} />
            Configure Settings
          </button>
        </nav>

        <button
          type="button"
          onClick={() => void handleAdminLogout()}
          className={styles.logoutBtn}
        >
          <LogoutOutlined className={styles.navIcon} />
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

export default AdminView;
