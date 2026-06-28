import React from 'react';
import { Header } from '../components/ui/Header';
import { ValidationTabSessionGuard } from '../pages/validation/ValidationTabSessionGuard';
import styles from './BaseLayout.module.scss';

interface BaseLayoutProps {
  children: React.ReactNode;
}

export const BaseLayout: React.FC<BaseLayoutProps> = ({ children }) => {
  return (
    <div className={styles.shell}>
      <Header />
      <ValidationTabSessionGuard />

      <main className={styles.main}>
        {children}
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div className={styles.footerBrand}>
            <span className={styles.footerTitle}>Pegasus</span>
            <span className={styles.footerCopy}>© 2026 Pegasus </span>
          </div>
        </div>
      </footer>
    </div>
  );
};
