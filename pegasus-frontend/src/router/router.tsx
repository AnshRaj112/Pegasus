import React, { lazy, Suspense } from 'react';
import { createHashRouter, Navigate } from 'react-router-dom';
import { Spin } from 'antd';

import AuthGuard from '~/components/auth-guard/AuthGuard';
import AppShell from '~/layouts/AppShell';
import Login from '~/pages/auth/Login';
import { PATHS } from '~/router/router.constants';
import NotFoundPage from '~/router/NotFoundPage';

const Dashboard = lazy(() => import('~/pages/dashboard/Dashboard'));
const ValidationWizardView = lazy(() => import('~/pages/validation/ValidationWizardView'));
const Report = lazy(() => import('~/pages/report/Report'));
const AdminView = lazy(() => import('~/pages/admin/AdminView'));
const SnippetViewRouter = lazy(() => import('~/pages/report/views/SnippetViewRouter'));
const ExecutionHistory = lazy(() => import('~/pages/report/views/ExecutionHistory'));
const Profile = lazy(() => import('~/pages/profile/Profile'));
const WorkspaceMgmtSubView = lazy(() => import('~/pages/admin/sections/WorkspaceMgmtSubView'));
const ConfigureStoreSubView = lazy(() => import('~/pages/admin/sections/ConfigureStoreSubView'));
const Setting = lazy(() => import('~/pages/admin/sections/setting/Setting'));

const LazyRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Suspense
    fallback={
      <div className="d-flex justify-content-center align-items-center min-vh-100">
        <Spin size="large" />
      </div>
    }
  >
    {children}
  </Suspense>
);

export const router = createHashRouter([
  {
    path: PATHS.LOGIN,
    element: <Login />,
  },
  {
    element: <AuthGuard />,
    children: [
      {
        element: <AppShell />,
        children: [
          {
            path: PATHS.DASHBOARD,
            element: (
              <LazyRoute>
                <Dashboard />
              </LazyRoute>
            ),
          },
          {
            path: PATHS.VALIDATIONS_WILDCARD,
            element: (
              <LazyRoute>
                <ValidationWizardView />
              </LazyRoute>
            ),
          },
          {
            path: PATHS.REPORTS,
            element: (
              <LazyRoute>
                <Report />
              </LazyRoute>
            ),
          },
          {
            path: PATHS.REPORT_HISTORY,
            element: (
              <LazyRoute>
                <ExecutionHistory />
              </LazyRoute>
            ),
          },
          {
            path: PATHS.REPORT_SNIPPET,
            element: (
              <LazyRoute>
                <SnippetViewRouter />
              </LazyRoute>
            ),
          },
          {
            path: PATHS.ADMIN,
            element: (
              <LazyRoute>
                <AdminView />
              </LazyRoute>
            ),
            children: [
              {
                index: true,
                element: <Navigate to="workspace-management" replace />,
              },
              {
                path: 'workspace-management',
                element: (
                  <LazyRoute>
                    <WorkspaceMgmtSubView />
                  </LazyRoute>
                ),
              },
              {
                path: 'configure-store',
                element: (
                  <LazyRoute>
                    <ConfigureStoreSubView />
                  </LazyRoute>
                ),
              },
              {
                path: 'settings',
                element: (
                  <LazyRoute>
                    <Setting />
                  </LazyRoute>
                ),
              },
            ],
          },
          {
            path: PATHS.PROFILE,
            element: (
              <LazyRoute>
                <Profile />
              </LazyRoute>
            ),
          },
          {
            path: PATHS.SETTING,
            element: (
              <LazyRoute>
                <Setting />
              </LazyRoute>
            ),
          },
          {
            path: '*',
            element: <NotFoundPage />,
          },
        ],
      },
    ],
  },
]);
