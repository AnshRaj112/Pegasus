import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { UserOutlined, LogoutOutlined } from '@ant-design/icons';
import headerIcon from '~/assets/icon.png';
import styles from './Header.module.scss';

export const Header: React.FC = () => {
  const location = useLocation();
  const currentPath = location.pathname;

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const getLinkClass = (path: string): string => {
    if (path === '/') {
      return currentPath === '/' ? styles.navLinkActive : styles.navLink;
    }
    const active = currentPath === path || currentPath.startsWith(`${path}/`);
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
        
        {/* Left Side: Brand Identity */}
        <div className={styles.brandIdentity}>
          <span className={styles.brandTitle}>Pegasus</span>
          <img src={headerIcon} alt="Pegasus Icon" className={styles.brandIcon} />
        </div>

        {/* Center: Nav Links */}
        <div className={styles.navLinks}>
          <Link to="/" className={getLinkClass('/')}>Dashboard</Link>
          <Link to="/validations" className={getLinkClass('/validations')}>Validations</Link>
          <Link to="/reports" className={getLinkClass('/reports')}>Reports</Link>
          <Link to="/admin" className={getLinkClass('/admin')}>Admin</Link>
        </div>

        {/* Right Side: Quick Actions */}
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

                <div className={styles.dropdownDivider} />

                <button
                  className={styles.dropdownItem}
                  onClick={() => {
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