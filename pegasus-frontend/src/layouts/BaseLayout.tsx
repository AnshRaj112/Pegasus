import React from 'react';
import { Header } from '../components/ui/Header'; // Imported here globally

interface BaseLayoutProps {
  children: React.ReactNode;
}

export const BaseLayout: React.FC<BaseLayoutProps> = ({ children }) => {
  return (
    <div style={{
      background: 'var(--background)',
      color: 'var(--on-background)',
      fontFamily: 'var(--font-body-md)',
      fontSize: 'var(--body-md)',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Dynamic persistent header layer */}
      <Header />

      {/* Main Workspace Frame container */}
      <main style={{
        flexGrow: 1,
        width: '100%',
        padding: 'var(--xl) var(--gutter)',
        maxWidth: 'var(--container-max)',
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--lg)'
      }}>
        {children}
      </main>

      {/* Footer Scaffolding */}
      <footer style={{ background: 'var(--surface-container)', borderTop: '1px solid var(--surface-variant)', marginTop: 'var(--xl)' }}>
        <div style={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          width: '100%',
          padding: 'var(--md) var(--gutter)',
          maxWidth: 'var(--container-max)',
          margin: '0 auto'
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--xs)' }}>
            <span style={{ fontFamily: 'var(--font-h3)', fontSize: 'var(--h3)', color: 'var(--on-surface)' }}>Pegasus</span>
            <span style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>© 2026 Pegasus </span>
          </div>
        </div>
      </footer>
    </div>
  );
};
