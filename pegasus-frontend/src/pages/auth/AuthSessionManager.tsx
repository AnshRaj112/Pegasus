import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Modal } from 'antd';

import { useAppDispatch, useAppSelector } from '../../redux/store';
import { authActions } from './Auth.reducer';
import { resetValidationOnLogout } from '../validation/resetValidationOnLogout';
import {
  adminLogout,
  extendAdminSession,
  fetchAdminMe,
  fetchAdminSessionStatus,
} from '../../shared/api/adminAuth';

const WARNING_WINDOW_MS = 5 * 60 * 1000;
const SESSION_POLL_MS = 30 * 1000;

export const AuthSessionManager: React.FC = () => {
  const dispatch = useAppDispatch();
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated);
  const isLoading = useAppSelector((state) => state.auth.isLoading);

  const [expiresAtMs, setExpiresAtMs] = useState<number | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [countdownMs, setCountdownMs] = useState(WARNING_WINDOW_MS);
  const forceLogoutAtRef = useRef<number | null>(null);

  const forceLogout = useCallback(async () => {
    try {
      await adminLogout();
    } finally {
      setShowPrompt(false);
      setExpiresAtMs(null);
      forceLogoutAtRef.current = null;
      resetValidationOnLogout(dispatch);
      dispatch(authActions.logoutSuccess());
    }
  }, [dispatch]);

  const refreshSessionStatus = useCallback(async () => {
    try {
      const status = await fetchAdminSessionStatus();
      const nextExpiry = new Date(status.expires_at).getTime();
      setExpiresAtMs(nextExpiry);
    } catch {
      await forceLogout();
    }
  }, [forceLogout]);

  useEffect(() => {
    let cancelled = false;
    const bootstrap = async () => {
      try {
        const me = await fetchAdminMe();
        if (!cancelled) dispatch(authActions.setSession({ email: me.email }));
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
    if (!isAuthenticated) return;
    void refreshSessionStatus();
    const interval = window.setInterval(() => {
      void refreshSessionStatus();
    }, SESSION_POLL_MS);
    return () => {
      window.clearInterval(interval);
    };
  }, [isAuthenticated, refreshSessionStatus]);

  useEffect(() => {
    if (!isAuthenticated || expiresAtMs == null) {
      setShowPrompt(false);
      forceLogoutAtRef.current = null;
      return;
    }
    const remaining = expiresAtMs - Date.now();
    if (remaining <= 0) {
      void forceLogout();
      return;
    }
    if (remaining <= WARNING_WINDOW_MS) {
      setShowPrompt(true);
      forceLogoutAtRef.current = Date.now() + Math.min(WARNING_WINDOW_MS, remaining);
      setCountdownMs(Math.min(WARNING_WINDOW_MS, remaining));
    } else {
      setShowPrompt(false);
      forceLogoutAtRef.current = null;
    }
  }, [expiresAtMs, forceLogout, isAuthenticated]);

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
      open={!isLoading && isAuthenticated && showPrompt}
      closable={false}
      maskClosable={false}
      title="Session expiring soon"
      okText="Extend 30 minutes"
      cancelText="Logout"
      onOk={() => {
        void extendAdminSession().then((status) => {
          setShowPrompt(false);
          forceLogoutAtRef.current = null;
          setExpiresAtMs(new Date(status.expires_at).getTime());
        }).catch(async () => {
          await forceLogout();
        });
      }}
      onCancel={() => {
        void forceLogout();
      }}
    >
      <p style={{ marginBottom: 0 }}>
        Your session will end soon. Extend now to stay logged in, or you will be logged out automatically in {countdownLabel}.
      </p>
    </Modal>
  );
};
