import React from 'react';
import { RouterProvider } from 'react-router-dom';

import { AuthSessionManager } from '~/pages/auth/AuthSessionManager';
import { router } from '~/router/router';

const App: React.FC = () => (
  <>
    <AuthSessionManager />
    <RouterProvider router={router} />
  </>
);

export default App;
