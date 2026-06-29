import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Modal } from 'antd';
import { useAppDispatch, useAppSelector } from '../../redux/store';
import { authActions } from './Auth.reducer';
import styles from './AuthSessionManager.module.scss';
import { resetValidationOnLogout } from '../validation/resetValidationOnLogout';
import {
  adminLogout,
  extendAdminSession,
  fetchAdminMe,
} from '../../shared/api/adminAuth';
import {
  getLastSessionActivityMs,
  registerSessionExtender,
  resetSessionActivity,
} from '../../shared/api/sessionActivity';

const INACTIVITY_MS = 15 * 60 * 1000;
const PROMPT_GRACE_MS = 5 * 60 * 1000;
const INACTIVITY_CHECK_MS = 10 * 1000;
const SESSION_BOOTSTRAP_TIMEOUT_MS = 8_000;

const withTimeout = <T,>(promise: Promise<T>, timeoutMs: number): Promise<T> =>
  new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      reject(new Error('Session bootstrap timed out'));
    }, timeoutMs);

    promise
      .then((value) => {
        window.clearTimeout(timer);
        resolve(value);
      })
      .catch((error: unknown) => {
        window.clearTimeout(timer);
        reject(error);
      });
  });

export const AuthSessionManager: React.FC = () => {
  const dispatch = useAppDispatch();
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated);
  const isFetching = useAppSelector((state) => state.auth.isFetching);

  const [showPrompt, setShowPrompt] = useState(false);
  const [countdownMs, setCountdownMs] = useState(PROMPT_GRACE_MS);
  const forceLogoutAtRef = useRef<number | null>(null);
  const showPromptRef = useRef(false);
  showPromptRef.current = showPrompt;

  const forceLogout = useCallback(async () => {
    try {
      await adminLogout();
    } finally {
      setShowPrompt(false);
      forceLogoutAtRef.current = null;
      resetValidationOnLogout(dispatch);
      dispatch(authActions.logoutSuccess());
    }
  }, [dispatch]);

  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      try {
        const me = await withTimeout(fetchAdminMe(), SESSION_BOOTSTRAP_TIMEOUT_MS);
        if (!cancelled) {
          resetSessionActivity();
          dispatch(authActions.setSession({ email: me.email }));
        }
      } catch {
        if (!cancelled) dispatch(authActions.setSession(null));
      }
    };
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  useEffect(() => {
    if (!isAuthenticated) {
      registerSessionExtender(null);
      return;
    }
    registerSessionExtender(async () => {
      await extendAdminSession();
    });
    return () => {
      registerSessionExtender(null);
    };
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    resetSessionActivity();
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated || isFetching) return;

    const checkInactivity = () => {
      const idleMs = Date.now() - getLastSessionActivityMs();
      if (idleMs >= INACTIVITY_MS) {
        if (!showPromptRef.current) {
          setShowPrompt(true);
          forceLogoutAtRef.current = Date.now() + PROMPT_GRACE_MS;
          setCountdownMs(PROMPT_GRACE_MS);
        }
      } else if (showPromptRef.current) {
        setShowPrompt(false);
        forceLogoutAtRef.current = null;
      }
    };

    checkInactivity();
    const interval = window.setInterval(checkInactivity, INACTIVITY_CHECK_MS);
    return () => {
      window.clearInterval(interval);
    };
  }, [isAuthenticated, isFetching]);

  useEffect(() => {
    if (!showPrompt) return;
    const interval = window.setInterval(() => {
      const forceLogoutAt = forceLogoutAtRef.current;
      if (!forceLogoutAt) return;
      const remaining = forceLogoutAt - Date.now();
      if (remaining <= 0) {
        window.clearInterval(interval);
        void forceLogout();
        return;
      }
      setCountdownMs(remaining);
    }, 1000);
    return () => {
      window.clearInterval(interval);
    };
  }, [forceLogout, showPrompt]);

  const countdownLabel = useMemo(() => {
    const totalSeconds = Math.max(0, Math.ceil(countdownMs / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${String(seconds).padStart(2, '0')}`;
  }, [countdownMs]);

  return (
    <Modal
      className={styles.sessionModal}
      open={!isFetching && isAuthenticated && showPrompt}
      closable={false}
      maskClosable={false}
      centered
      title="Session expiring soon"
      okText="Extend session"
      cancelText="Logout"
      onOk={() => {
        void extendAdminSession().then(() => {
          resetSessionActivity();
          setShowPrompt(false);
          forceLogoutAtRef.current = null;
        }).catch(async () => {
          await forceLogout();
        });
      }}
      onCancel={() => {
        void forceLogout();
      }}
    >
      <p className={styles.modalText}>
        You have been inactive for 15 minutes. Extend your session to stay logged in, or you will be logged out automatically in {countdownLabel}.
      </p>
    </Modal>
  );
};
