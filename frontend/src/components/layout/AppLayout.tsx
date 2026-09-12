/**
 * MedFusion AI — Application Layout Wrapper
 */

import React from "react";
import { Outlet } from "react-router-dom";
import { Navbar } from "./Navbar";
import { RegulatoryDisclaimer } from "../common/RegulatoryDisclaimer";

export const AppLayout: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 antialiased">
      <Navbar />

      {/* Mandatory Top Regulatory Notice */}
      <div className="border-b border-amber-200/60 bg-amber-50/50">
        <div className="mx-auto max-w-7xl px-4 py-1.5 sm:px-6 lg:px-8">
          <RegulatoryDisclaimer compact />
        </div>
      </div>

      {/* Main Content Body */}
      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <Outlet />
        </div>
      </main>

      {/* Institutional Compliance Footer */}
      <footer className="border-t border-gray-200 bg-white py-6">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 text-xs text-gray-500 sm:flex-row sm:px-6 lg:px-8">
          <p>
            &copy; {new Date().getFullYear()} MedFusion AI &bull; Assistive Multimodal Clinical Decision Support System.
          </p>
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5 text-emerald-700 font-medium">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              DenseNet-121 / ResNet-50 Gated Late Fusion Active
            </span>
            <span>&bull;</span>
            <span className="text-gray-400">HIPAA De-identified (SHA-256)</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
