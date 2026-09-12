/**
 * MedFusion AI — Protected Route Guard Component
 */

import React, { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../../stores/auth.store";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { UserRole } from "../../types";

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { isAuthenticated, user, isLoading, fetchCurrentUser } = useAuthStore();
  const location = useLocation();

  useEffect(() => {
    if (isAuthenticated && !user) {
      fetchCurrentUser().catch(() => {});
    }
  }, [isAuthenticated, user, fetchCurrentUser]);

  if (isLoading && !user) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-gray-50">
        <LoadingSpinner size="lg" message="Verifying clinical session credentials..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-gray-50 p-6 text-center">
        <div className="max-w-md rounded-2xl border border-rose-200 bg-white p-8 shadow-sm">
          <h2 className="text-xl font-bold text-rose-600">Access Restricted</h2>
          <p className="mt-2 text-sm text-gray-600">
            Your user role (<strong>{user.role}</strong>) does not have sufficient permissions to view this diagnostic workstation view.
          </p>
          <button
            onClick={() => window.history.back()}
            className="mt-6 rounded-lg bg-gray-900 px-4 py-2 text-xs font-semibold text-white hover:bg-gray-800"
          >
            Return to Authorized Dashboard
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
