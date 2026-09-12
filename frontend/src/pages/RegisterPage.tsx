/**
 * MedFusion AI — Staff Registration Page
 */

import React from "react";
import { RegisterForm } from "../components/auth/RegisterForm";
import { RegulatoryDisclaimer } from "../components/common/RegulatoryDisclaimer";

export const RegisterPage: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col justify-between bg-slate-900 text-slate-100">
      <div className="border-b border-slate-800 bg-slate-950/60 py-2">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <RegulatoryDisclaimer compact />
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center p-4">
        <RegisterForm />
      </div>

      <div className="border-t border-slate-800 py-4 text-center text-xs text-slate-500">
        &copy; {new Date().getFullYear()} MedFusion AI &bull; Assistive Clinical Decision Support System.
      </div>
    </div>
  );
};
