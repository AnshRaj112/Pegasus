import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { Spin } from 'antd';

import { useAppSelector } from '~/redux/store';
import { PATHS } from '~/router/router.constants';

const AuthGuard: React.FC = () => {
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated);
  const isFetching = useAppSelector((state) => state.auth.isFetching);

  if (isFetching) {
    return (
      <div className="d-flex justify-content-center align-items-center min-vh-100">
        <Spin size="large" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to={PATHS.LOGIN} replace />;
  }

  return <Outlet />;
};

export default AuthGuard;
