import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { AppRoutes } from './routes/AppRoutes.tsx';
import { AuthSessionManager } from './pages/auth/AuthSessionManager.tsx';
import './styles/tokens.css';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthSessionManager />
      <AppRoutes />
    </BrowserRouter>
  );
};

export default App;
