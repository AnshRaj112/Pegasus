import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { BaseLayout } from '../layouts/BaseLayout';
import { Dashboard } from '../pages/dashboard/Dashboard';
import { ValidationWizardView } from '../pages/validation/ValidationWizardView';
import { HistoryView } from '../pages/history/HistoryView';
import { AdminView } from '../pages/admin/AdminView';
import { ValidationReport } from '../pages/validation/components/ValidationReport';
import { Login } from '../pages/auth/Login';
import { ProtectedRoute } from './ProtectedRoute';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/*" element={
          <BaseLayout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/validations" element={<ValidationWizardView />} />
              <Route path="/history" element={<HistoryView />} />
              <Route path="/validation/report/:jobId" element={<ValidationReport onBack={() => window.history.back()} />} />
              <Route path="/admin" element={<AdminView />} />
              <Route path="*" element={<div style={{ color: 'var(--on-surface)', padding: 'var(--lg)' }}>404 Error: Section View Not Found</div>} />
            </Routes>
          </BaseLayout>
        } />
      </Route>
    </Routes>
  );
};