import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import styles from './Header.module.scss';

export const Header: React.FC = () => {
  const location = useLocation();
  const currentPath = location.pathname;

  const getLinkClass = (path: string): string =>
    currentPath === path ? styles.navLinkActive : styles.navLink;

  return (
    <nav className={styles.header}>
      <div className={styles.inner}>
        {/* Branding Title + Nav Links — Onyx Red branding per palette */}
        <div className={styles.brandGroup}>
          <span className={styles.brandTitle}>Pegasus</span>
          <div className={styles.navLinks}>
            <Link to="/" className={getLinkClass('/')}>Dashboard</Link>
            <Link to="/validations" className={getLinkClass('/validations')}>Validations</Link>
            {/* Admin Workspace panel */}
            <Link to="/admin" className={getLinkClass('/admin')}>Admin</Link>
            <Link to="/history" className={getLinkClass('/history')}>History</Link>
            <Link to="/reports" className={getLinkClass('/reports')}>Reports</Link>
          </div>
        </div>

        {/* Shared Quick Actions Area */}
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
          <img
            alt="Profile Avatar"
            className={styles.avatar}
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuDBZhdsvY8UoOClzZZSWqP_e1f10fDQH3S329Fqt8U1mE_x0qkSmL0sqwzXd4UPavjsg7zyWEUECcr5AB-9lefgvfCCg3i7KCIbTh2dtc0YUvR9kph-I3RmAVuc0lAojPROCyebE38Llzj2Wh4Gf9Q43R-0x5dQ1EWSsUTpe0aUbJfwiEWN8iuE-JREpY7Chkx3m_n-W0kDTriINmZHMEUxcXfhPN_BMIh1bW3Cz4zvGsuhVcGvjikyD5Uh3rqPnx4uQgo0yu6GXVk"
          />
        </div>
      </div>
    </nav>
  );
};