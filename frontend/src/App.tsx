/**
 * MedFusion AI — Root Application Routing & Component Tree
 */

import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { AppLayout } from "./components/layout/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { CasesPage } from "./pages/CasesPage";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { NewCasePage } from "./pages/NewCasePage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AuditPage } from "./pages/AuditPage";
import { UserRole } from "./types";

function App() {
  return (
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
  );
}

export default App;
