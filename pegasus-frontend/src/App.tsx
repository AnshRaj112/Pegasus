import React from 'react';
import { RouterProvider } from 'react-router-dom';

import { AuthSessionManager } from '~/pages/auth/AuthSessionManager';
import HashPathGuard from '~/router/HashPathGuard';
import { router } from '~/router/router';

const App: React.FC = () => (
  <HashPathGuard>
    <AuthSessionManager />
    <RouterProvider router={router} />
  </HashPathGuard>
);

export default App;
