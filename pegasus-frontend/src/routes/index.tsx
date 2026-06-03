import React from 'react'
import { Navigate, RouteObject } from 'react-router-dom'
import { AppLayout } from '../layouts/AppLayout'
import DashboardPage from '../pages/DashboardPage'
import InternalDashboardPage from '../pages/InternalDashboardPage'
import ValidationSelectorPage from '../pages/ValidationSelectorPage'
import ConfigureMappingPage from '../pages/ConfigureMappingPage'
import HistoryPage from '../pages/HistoryPage'
import AdminLayout from '../pages/admin/AdminLayout'
import WorkspaceManagementPage from '../pages/admin/WorkspaceManagementPage'
import ConfigureStorePage from '../pages/admin/ConfigureStorePage'
import DetailedReportPage from '../pages/DetailedReportPage'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'dashboard/:entityId', element: <InternalDashboardPage /> },
      { path: 'validation', element: <ValidationSelectorPage /> },
      { path: 'configure-mapping', element: <ConfigureMappingPage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'report', element: <DetailedReportPage /> },
      {
        path: 'admin',
        element: <AdminLayout />,
        children: [
          { index: true, element: <Navigate to="/admin/workspaces" replace /> },
          { path: 'workspaces', element: <WorkspaceManagementPage /> },
          { path: 'store', element: <ConfigureStorePage /> },
        ],
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
]
