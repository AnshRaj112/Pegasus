import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export const Header: React.FC = () => {
  const location = useLocation();
  const currentPath = location.pathname;

  // Reusable styling utility for unhighlighted menu buttons
  const linkBaseStyle: React.CSSProperties = {
    color: 'var(--on-surface-variant)',
    fontFamily: 'var(--font-label-md)',
    fontSize: 'var(--label-md)',
    textDecoration: 'none',
    fontWeight: 500,
    transition: 'color 0.2s, border-color 0.2s'
  };

  // Reusable styling utility for active menu buttons
  const activeLinkStyle: React.CSSProperties = {
    ...linkBaseStyle,
    color: 'var(--primary)',
    borderBottom: '2px solid var(--primary)',
    paddingBottom: '4px'
  };

  return (
    <nav style={{
      background: 'var(--surface)',
      borderBottom: '1px solid var(--surface-variant)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      width: '100%',             // ⚡ FIX: Force it to span the full screen
      boxSizing: 'border-box',   // ⚡ FIX: Keep borders from bleeding
      flexShrink: 0              // ⚡ FIX: Stop the flexbox BaseLayout from squishing it vertically
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        width: '100%',
        padding: '0 var(--gutter)',
        maxWidth: 'var(--container-max)',
        margin: '0 auto',
        height: '64px',
        boxSizing: 'border-box'  // ⚡ FIX: Stop horizontal padding bleed here as well
      }}>
        {/* Branding Title Platform Anchor */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--xl)' }}>
          <span style={{ fontFamily: 'var(--font-h2)', fontSize: 'var(--h2)', fontWeight: 900, color: 'var(--primary)' }}>
            Pegasus
          </span>
          <div style={{ display: 'flex', gap: 'var(--lg)', alignItems: 'center' }}>
            <Link to="/" style={currentPath === '/' ? activeLinkStyle : linkBaseStyle}>Dashboard</Link>
            <Link to="/validations" style={currentPath === '/validations' ? activeLinkStyle : linkBaseStyle}>Validations</Link>
            {/* Renamed Link targeting the upcoming Admin Workspace panel */}
            <Link to="/admin" style={currentPath === '/admin' ? activeLinkStyle : linkBaseStyle}>Admin</Link>
            <Link to="/history" style={currentPath === '/history' ? activeLinkStyle : linkBaseStyle}>History</Link>
            {/* ❌ Settings Option completely removed from the DOM list */}
          </div>
        </div>
        
        {/* Shared Quick Actions Area */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--md)' }}>
          <span className="material-symbols-outlined" style={{ color: 'var(--on-surface-variant)', cursor: 'pointer', padding: 'var(--xs)', borderRadius: '50%' }}>Notifications</span>
          <span className="material-symbols-outlined" style={{ color: 'var(--on-surface-variant)', cursor: 'pointer', padding: 'var(--xs)', borderRadius: '50%' }}>Help</span>
          <img 
            alt="Profile Avatar" 
            style={{ width: '32px', height: '32px', borderRadius: '50%', border: '1px solid var(--surface-variant)', objectFit: 'cover' }}
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuDBZhdsvY8UoOClzZZSWqP_e1f10fDQH3S329Fqt8U1mE_x0qkSmL0sqwzXd4UPavjsg7zyWEUECcr5AB-9lefgvfCCg3i7KCIbTh2dtc0YUvR9kph-I3RmAVuc0lAojPROCyebE38Llzj2Wh4Gf9Q43R-0x5dQ1EWSsUTpe0aUbJfwiEWN8iuE-JREpY7Chkx3m_n-W0kDTriINmZHMEUxcXfhPN_BMIh1bW3Cz4zvGsuhVcGvjikyD5Uh3rqPnx4uQgo0yu6GXVk"
          />
        </div>
      </div>
    </nav>
  );
};