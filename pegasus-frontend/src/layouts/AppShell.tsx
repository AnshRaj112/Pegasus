import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import { BaseLayout } from '~/layouts/BaseLayout';
import { ValidationHistoryNavigation } from '~/pages/validation/ValidationHistoryNavigation';

const isFullHeightRoute = (pathname: string): boolean =>
  pathname.startsWith('/validations') || pathname.startsWith('/reports');

const AppShell: React.FC = () => {
  const { pathname } = useLocation();
  const fullHeight = isFullHeightRoute(pathname);

  return (
    <BaseLayout fullHeight={fullHeight}>
      <ValidationHistoryNavigation />
      <Outlet />
    </BaseLayout>
  );
};

export default AppShell;
