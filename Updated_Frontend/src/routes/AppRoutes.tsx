import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { BaseLayout } from '../layouts/BaseLayout';
import { Dashboard } from '../pages/dashboard/Dashboard';
import { ValidationWizardView } from '../pages/validation/ValidationWizardView';
import { HistoryView } from '../views/history/HistoryView';
import { AdminView } from '../views/admin/AdminView'; // Imported here!
import { ValidationReport } from '../pages/validation/components/ValidationReport';

export const AppRoutes: React.FC = () => {
  return (
    <BaseLayout>
      <Routes>
        {/* Persistent Path Mappings */}
        <Route path="/" element={<Dashboard />} />
        <Route path="/validations" element={<ValidationWizardView />} />
        <Route path="/history" element={<HistoryView />} />
        <Route path="/validation/report/:jobId" element={<ValidationReport onBack={() => window.history.back()} />} />
        
        {/* Full Modular Administrative Workspace Center */}
        <Route path="/admin" element={<AdminView />} />
        
        {/* Catch-all Layout Boundary Fallback */}
        <Route path="*" element={<div style={{ color: 'var(--on-surface)', padding: 'var(--lg)' }}>404 Error: Section View Not Found</div>} />
      </Routes>
    </BaseLayout>
  );
};
