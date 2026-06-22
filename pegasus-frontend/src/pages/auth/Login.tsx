import React, { useState } from 'react';
import { 
  MailOutlined, 
  LockOutlined, 
  EyeOutlined, 
  EyeInvisibleOutlined, 
  LoginOutlined, 
  QuestionCircleOutlined
} from '@ant-design/icons';
import styles from './Auth.module.scss';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '../../redux/store';
import { authActions } from './Auth.reducer';
import { adminLogin } from '../../shared/api/adminAuth';
import { getApiErrorMessage } from '../../shared/api/apiError';

export const Login: React.FC = () => {
  const navigate = useNavigate(); // ⚡ Initialize router
  const dispatch = useAppDispatch(); // ⚡ Initialize Redux
  
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
      navigate('/');
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Sign-in failed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={`${styles.authWrapper} ${styles.glassBackground}`}>
      <header className={styles.authHeader}>
        <div className={styles.authLogo}>Pegasus</div>
        <QuestionCircleOutlined className={styles.authHelpIcon} />
      </header>

      <main className={styles.authMain}>
        <div className={styles.authCard}>
          <div className={styles.authCardHeader}>
            <h1 className={styles.authCardTitle}>Welcome Back</h1>
            <p className={styles.authCardSubtitle}>Enter your credentials to access your data audits</p>
          </div>

          <form onSubmit={handleSubmit} className={styles.authForm}>
            <div>
              <label className={styles.authFormLabel}>Email Address</label>
              <div className={styles.inputWrapper}>
                <MailOutlined className={styles.inputIcon} />
                <input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={styles.authInput} 
                  placeholder="name@company.com" 
                  required
                  autoComplete="username"
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className={styles.authFormLabel}>Password</label>
                <a href="#" className={styles.authFormForgotLink}>Forgot password?</a>
              </div>
              <div className={styles.inputWrapper}>
                <LockOutlined className={styles.inputIcon} />
                <input 
                  type={showPassword ? "text" : "password"} 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={styles.authInput} 
                  style={{ paddingRight: '40px' }}
                  placeholder="••••••••" 
                  required
                  autoComplete="current-password"
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className={styles.actionIcon}>
                  {showPassword ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                </button>
              </div>
            </div>

            {error && <p className={styles.authFormError}>{error}</p>}

            <button type="submit" className={styles.submitBtn} disabled={isSubmitting}>
              {isSubmitting ? 'Signing in...' : <>Sign In <LoginOutlined style={{ fontSize: '18px' }} /></>}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
};