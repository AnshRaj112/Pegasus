import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { BaseLayout } from '../layouts/BaseLayout';
import { ValidationHistoryNavigation } from '../pages/validation/ValidationHistoryNavigation';
import { Dashboard } from '../pages/dashboard/Dashboard';
import { ValidationWizardView } from '../pages/validation/ValidationWizardView';
import { Report } from '../pages/report/Report';
import { AdminView } from '../pages/admin/AdminView';
import { Login } from '../pages/auth/Login';
import { ProtectedRoute } from './ProtectedRoute';
import { SnippetViewRouter } from '../pages/report/views/SnippetViewRouter';
import { ExecutionHistory } from '../pages/report/views/ExecutionHistory';
import Profile from '../pages/profile/Profile';
import { WorkspaceMgmtSubView } from '../pages/admin/sections/WorkspaceMgmtSubView';
import { ConfigureStoreSubView } from '../pages/admin/sections/ConfigureStoreSubView';
import Setting from '~/pages/admin/sections/setting/Setting';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/*" element={
          <BaseLayout>
            <ValidationHistoryNavigation />
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/validations/*" element={<ValidationWizardView />} />
              <Route path="/reports" element={<Report />} />
              <Route path="/reports/:mappingId/history" element={<ExecutionHistory />} />
              <Route path="/reports/:mappingId/history/:runId/snippet" element={<SnippetComparison />} />
              <Route path="/admin" element={<AdminView />}>
                {/* Default redirect to workspace management */}
                <Route index element={<Navigate to="workspace-management" replace />} />
                <Route path="workspace-management" element={<WorkspaceMgmtSubView />} />
                <Route path="configure-store" element={<ConfigureStoreSubView />} />
                <Route path="settings" element={<Setting />} />
              </Route>
              <Route path="/reports/:mappingId/history/:runId/snippet" element={<SnippetViewRouter />} />
              <Route path="/admin" element={<AdminView />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/setting" element={<Setting />} />
              <Route path="*" element={<div style={{ color: 'var(--on-surface)', padding: 'var(--lg)' }}>404 Error: Section View Not Found</div>} />
            </Routes>
          </BaseLayout>
        } />
      </Route>
    </Routes>
  );
};
