/**
 * MedFusion AI — Concordance & Quality Assurance Analytics Page
 */

import React from "react";
import { ConcordanceDashboard } from "../components/analytics/ConcordanceDashboard";

export const AnalyticsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <ConcordanceDashboard />
    </div>
  );
};
