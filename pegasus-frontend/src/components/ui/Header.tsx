import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { UserOutlined, LogoutOutlined, SettingOutlined } from '@ant-design/icons';

import headerIcon from '~/assets/icon.png';
import styles from './Header.module.scss';

export const Header: React.FC = () => {
  const location = useLocation();
  const currentPath = location.pathname;

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const getLinkClass = (path: string): string => {
    const active = path === '/validations'
      ? currentPath === '/validations' || currentPath.startsWith('/validations/')
      : currentPath === path;
    return active ? styles.navLinkActive : styles.navLink;
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <nav className={styles.header}>
      <div className={styles.inner}>
        
        <div className={styles.brandGroup}>
          <div className="d-flex align-items-center">
            <span className={styles.brandTitle}>Pegasus</span>
            <img src={headerIcon} alt="Pegasus Icon" className={`ms-2 ${styles.brandIcon}`} />
          </div>
          <div className={styles.navLinks}>
            <Link to="/" className={getLinkClass('/')}>Dashboard</Link>
            <Link to="/validations" className={getLinkClass('/validations')}>Validations</Link>
            <Link to="/admin" className={getLinkClass('/admin')}>Admin</Link>
            <Link to="/reports" className={getLinkClass('/reports')}>Reports</Link>
          </div>
        </div>

        <div className={styles.quickActions}>
          <span
            className={`material-symbols-outlined ${styles.iconButton}`}
            role="button"
            aria-label="Notifications"
          >
            Notifications
          </span>
          <span
            className={`material-symbols-outlined ${styles.iconButton}`}
            role="button"
            aria-label="Help"
          >
            Help
          </span>

          <div className={styles.profileContainer} ref={dropdownRef}>
            <div
              className={styles.avatarWrapper}
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              role="button"
              aria-label="User Menu"
              data-testid="header-user-menu"
            >
              <UserOutlined className={styles.avatarIcon} />
            </div>

            {isDropdownOpen && (
              <div className={styles.dropdownMenu}>
                <Link
                  to="/profile"
                  className={styles.dropdownItem}
                  onClick={() => setIsDropdownOpen(false)}
                >
                  <UserOutlined />
                  <span>Profile</span>
                </Link>

                <Link 
                  to="/setting" 
                  className={styles.dropdownItem} 
                  onClick={() => setIsDropdownOpen(false)}
                >
                  <SettingOutlined />
                  <span>Setting</span>
                </Link>

                <div className={styles.dropdownDivider} />

                <button
                  className={styles.dropdownItem}
                  onClick={() => {
                    // TODO: Add your logout logic here
                    setIsDropdownOpen(false);
                  }}
                  data-testid="header-logout-btn"
                >
                  <LogoutOutlined />
                  <span>Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};