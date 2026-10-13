/** Audit UI intentionally shows no sample records until a real API is available. */

import React from "react";
import { ShieldAlert } from "lucide-react";

export const AuditPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight text-gray-900">
          Audit Trail
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Review recorded events when an audit-events service is available.
        </p>
      </div>

      <section
        role="status"
        aria-live="polite"
        className="rounded-2xl border border-amber-200 bg-amber-50 p-6 shadow-sm"
      >
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
          <div>
            <h2 className="font-bold text-amber-950">Audit history unavailable</h2>
            <p className="mt-1 text-sm text-amber-900">
              This build does not provide an audit-events API. No sample events,
              integrity claims, or regulatory-compliance status are shown here.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
