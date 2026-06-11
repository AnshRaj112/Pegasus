import React, { useState } from 'react';
import { 
  MailOutlined, 
  LockOutlined, 
  EyeOutlined, 
  EyeInvisibleOutlined, 
  LoginOutlined, 
  SafetyCertificateOutlined,
  QuestionCircleOutlined
} from '@ant-design/icons';
import styles from './Auth.module.scss';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch } from '../../redux/store';
import { authActions } from './Auth.reducer';

export const Login: React.FC = () => {
  const navigate = useNavigate(); // ⚡ Initialize router
  const dispatch = useAppDispatch(); // ⚡ Initialize Redux
  
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // ⚡ Simulate a successful API login response
    dispatch(authActions.loginSuccess({ 
      email: email, 
      fullName: 'Enterprise User' 
    }));
    
    // ⚡ Redirect them to the Dashboard
    navigate('/');
  };

  return (
    <div className={`${styles.authWrapper} ${styles.glassBackground}`}>
      <header style={{ width: '100%', height: '64px', borderBottom: '1px solid var(--outline-variant)', backgroundColor: 'var(--surface)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px' }}>
        <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--primary)' }}>Pegasus</div>
        <QuestionCircleOutlined style={{ fontSize: '20px', color: 'var(--on-surface-variant)', cursor: 'pointer' }} />
      </header>

      <main className={styles.authMain}>
        <div className={styles.authCard}>
          <div style={{ marginBottom: '32px', textAlign: 'center' }}>
            <h1 style={{ fontSize: '30px', fontWeight: 600, color: 'var(--on-surface)', margin: '0 0 4px 0' }}>Welcome Back</h1>
            <p style={{ fontSize: '14px', color: 'var(--on-surface-variant)', margin: 0 }}>Enter your credentials to access your data audits</p>
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div>
              <label style={{ fontSize: '14px', fontWeight: 500, color: 'var(--on-surface)' }}>Email Address</label>
              <div className={styles.inputWrapper}>
                <MailOutlined className={styles.inputIcon} />
                <input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={styles.authInput} 
                  placeholder="name@company.com" 
                  required 
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontSize: '14px', fontWeight: 500, color: 'var(--on-surface)' }}>Password</label>
                <a href="#" style={{ fontSize: '12px', color: 'var(--primary)', textDecoration: 'none' }}>Forgot password?</a>
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
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className={styles.actionIcon}>
                  {showPassword ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input type="checkbox" id="remember" style={{ accentColor: 'var(--primary)', cursor: 'pointer', width: '16px', height: '16px' }} />
              <label htmlFor="remember" style={{ fontSize: '14px', color: 'var(--on-surface-variant)', cursor: 'pointer', userSelect: 'none' }}>Remember this device for 30 days</label>
            </div>

            <button type="submit" className={styles.submitBtn}>
              Sign In <LoginOutlined style={{ fontSize: '18px' }} />
            </button>
          </form>
        </div>

        <div style={{ position: 'absolute', bottom: '100px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', opacity: 0.6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--on-surface)' }}>
            <SafetyCertificateOutlined style={{ fontSize: '16px' }} />
            <span style={{ fontSize: '12px' }}>Bank-grade data encryption</span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--on-surface)', margin: 0 }}>Trusted by 500+ data engineering teams worldwide.</p>
        </div>
      </main>
    </div>
  );
};