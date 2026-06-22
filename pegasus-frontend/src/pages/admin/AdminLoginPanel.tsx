import React, { useState } from 'react';
import { LockOutlined, MailOutlined, SafetyCertificateOutlined } from '@ant-design/icons';

import { adminLogin, adminSignup } from '../../shared/api/adminAuth';
import { getApiErrorMessage } from '../../shared/api/apiError';
import styles from '../auth/Auth.module.scss';

interface AdminLoginPanelProps {
  onSuccess: (email: string) => void;
}

export const AdminLoginPanel: React.FC<AdminLoginPanelProps> = ({ onSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignup, setIsSignup] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const user = isSignup
        ? await adminSignup(email.trim(), password)
        : await adminLogin(email.trim(), password);
      onSuccess(user.email);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Admin sign-in failed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 64px)', padding: 24 }}>
      <div className={styles.authCard}>
        <div style={{ marginBottom: 24, textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 48, height: 48, borderRadius: 12, backgroundColor: '#0057c2', color: '#fff', marginBottom: 12 }}>
            <SafetyCertificateOutlined style={{ fontSize: 24 }} />
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 600, margin: '0 0 8px' }}>Admin sign-in</h1>
          <p style={{ fontSize: 14, color: '#414755', margin: 0 }}>
            Required to manage GCS connections. This is separate from the main app login.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div>
            <label style={{ fontSize: 14, fontWeight: 500 }}>Email</label>
            <div className={styles.inputWrapper}>
              <MailOutlined className={styles.inputIcon} />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={styles.authInput}
                placeholder="admin@company.com"
                required
                autoComplete="username"
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: 14, fontWeight: 500 }}>Password</label>
            <div className={styles.inputWrapper}>
              <LockOutlined className={styles.inputIcon} />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={styles.authInput}
                placeholder="••••••••"
                required
                autoComplete={isSignup ? 'new-password' : 'current-password'}
              />
            </div>
          </div>

          {error && (
            <p style={{ margin: 0, fontSize: 13, color: '#ba1a1a' }}>{error}</p>
          )}

          <button type="submit" className={styles.submitBtn} disabled={isSubmitting}>
            {isSubmitting ? 'Please wait…' : isSignup ? 'Create admin account' : 'Sign in as admin'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => { setIsSignup((v) => !v); setError(null); }}
          style={{ marginTop: 16, width: '100%', background: 'none', border: 'none', color: '#234B5F', fontSize: 13, cursor: 'pointer' }}
        >
          {isSignup ? 'Already have an admin account? Sign in' : 'First-time setup? Create admin account'}
        </button>
      </div>
    </div>
  );
};
