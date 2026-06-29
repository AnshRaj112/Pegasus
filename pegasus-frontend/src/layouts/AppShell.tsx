import React from 'react';
import { Outlet } from 'react-router-dom';

import { BaseLayout } from '~/layouts/BaseLayout';
import { ValidationHistoryNavigation } from '~/pages/validation/ValidationHistoryNavigation';

const AppShell: React.FC = () => (
  <BaseLayout>
    <ValidationHistoryNavigation />
    <Outlet />
  </BaseLayout>
);

export default AppShell;
