/**
 * MedFusion AI — Root Application Routing & Component Tree
 */

import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { AppLayout } from "./components/layout/AppLayout";
import { UserRole } from "./types";

const LoginPage = lazy(() =>
  import("./pages/LoginPage").then((module) => ({ default: module.LoginPage })),
);
const RegisterPage = lazy(() =>
  import("./pages/RegisterPage").then((module) => ({ default: module.RegisterPage })),
);
const CasesPage = lazy(() =>
  import("./pages/CasesPage").then((module) => ({ default: module.CasesPage })),
);
const CaseDetailPage = lazy(() =>
  import("./pages/CaseDetailPage").then((module) => ({ default: module.CaseDetailPage })),
);
const NewCasePage = lazy(() =>
  import("./pages/NewCasePage").then((module) => ({ default: module.NewCasePage })),
);
const AnalyticsPage = lazy(() =>
  import("./pages/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })),
);
const AuditPage = lazy(() =>
  import("./pages/AuditPage").then((module) => ({ default: module.AuditPage })),
);

function App() {
  return (
    <Suspense
      fallback={
        <div
          role="status"
          aria-live="polite"
          className="flex min-h-screen items-center justify-center text-sm text-gray-600"
        >
          <span className="sr-only">Loading page</span>
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-primary-600" />
        </div>
      }
    >
      <Routes>
        {/* Public Authentication Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected Diagnostic & Clinical Workstation Routes */}
        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Navigate to="/cases" replace />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/new" element={<NewCasePage />} />
          <Route path="/cases/:id" element={<CaseDetailPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route
            path="/audit"
            element={
              <ProtectedRoute allowedRoles={[UserRole.ADMIN, UserRole.AUDITOR]}>
                <AuditPage />
              </ProtectedRoute>
            }
          />
        </Route>

        {/* Fallback Catch-all Route */}
        <Route path="*" element={<Navigate to="/cases" replace />} />
      </Routes>
    </Suspense>
  );
}

export default App;
