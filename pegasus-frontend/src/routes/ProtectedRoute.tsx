import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAppSelector } from '../redux/store';

export const ProtectedRoute: React.FC = () => {
  // Read the auth status from Redux
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated);

  if (!isAuthenticated) {
    // ⚡ If they aren't logged in, redirect them to the Login page
    return <Navigate to="/login" replace />;
  }

  // ⚡ If they ARE logged in, render the child routes normally
  return <Outlet />;
};