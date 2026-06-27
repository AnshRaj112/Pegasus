import React, { useState } from 'react';
import { 
  MailOutlined, 
  LockOutlined, 
  EyeOutlined, 
  EyeInvisibleOutlined 
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { useAppDispatch } from '~/redux/store';
import { authActions } from './Auth.reducer';
import { adminLogin } from '~/shared/api/adminAuth';
import { getApiErrorMessage } from '~/shared/api/apiError';
import { PATHS } from '~/router/router.constants';

import loginIcon from '~/assets/login_icon.png';
import onixLogo from '~/assets/logo.png';
import styles from './Auth.module.scss';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const user = await adminLogin(email.trim(), password);
      dispatch(authActions.setSession({ email: user.email }));
      navigate(PATHS.DASHBOARD);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Sign-in failed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={`${styles.authWrapper} ${styles.glassBackground}`}>
      {/* Background Watermark - Shifted Right */}
      <img 
        src={loginIcon} 
        alt="Pegasus Watermark" 
        className={styles.watermarkBg} 
        aria-hidden="true"
      />

      {/* Onix Top Logo - Pushed near the top */}
      <div className={styles.onixLogoWrapper}>
        <img src={onixLogo} alt="Onix Logo" className={styles.onixLogo} />
      </div>

      <main className={styles.authMain}>
        <div className={styles.authCard}>
          {/* Card Brand Header */}
          <div className="d-flex justify-content-center align-items-center mb-4">
            <img src={loginIcon} alt="Pegasus Logo" className={`me-3 ${styles.cardBrandIcon}`} />
            <div className="text-start d-flex flex-column justify-content-center">
              <h1 className={styles.authCardTitle}>Pegasus</h1>
              <span className={styles.authCardSubtitle}>The Validator</span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className={styles.authForm} data-testid="login-form">
            <div className="mb-3">
              <label className={styles.authFormLabel} htmlFor="email">
                <span className="text-danger">*</span> User
              </label>
              <div className={styles.inputWrapper}>
                <MailOutlined className={styles.inputIcon} />
                <input 
                  className={styles.authInput} 
                  type="email" 
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="User" 
                  required
                  autoComplete="username"
                  data-testid="input-email"
                />
              </div>
            </div>

            <div className="mb-4">
              <div className="d-flex justify-content-between align-items-center mb-1">
                <label className={styles.authFormLabel} htmlFor="password">
                  <span className="text-danger">*</span> Password
                </label>
              </div>
              <div className={styles.inputWrapper}>
                <LockOutlined className={styles.inputIcon} />
                <input 
                  className={`pe-5 ${styles.authInput}`} 
                  type={showPassword ? "text" : "password"} 
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Password" 
                  required
                  autoComplete="current-password"
                  data-testid="input-password"
                />
                <button 
                  className={styles.actionIcon}
                  type="button" 
                  onClick={() => setShowPassword(!showPassword)} 
                  aria-label="Toggle password visibility"
                  data-testid="btn-toggle-password"
                >
                  {showPassword ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                </button>
              </div>
              <div className="mt-2 text-start">
                <a href="#" className={styles.authFormForgotLink}>Forgot Password?</a>
              </div>
            </div>

            {error && <p className={styles.authFormError} data-testid="login-error-message">{error}</p>}

            <button 
              className={`mt-2 ${styles.submitBtn}`}
              type="submit" 
              disabled={isSubmitting}
              data-testid="btn-submit-login"
            >
              {isSubmitting ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        </div>
      </main>

      <footer className={styles.authFooter}>
        <p className="m-0 text-muted">© 2026 <strong>Onix</strong>. All rights reserved.</p>
      </footer>
    </div>
  );
};