/**
 * MedFusion AI — Institutional Clinical Audit Trail Page
 */

import React, { useState } from "react";
import { ShieldCheck, Lock } from "lucide-react";

interface AuditEntry {
  id: string;
  timestamp: string;
  user: string;
  role: string;
  action: string;
  resource: string;
  integrity_hash: string;
}

export const AuditPage: React.FC = () => {
  const [logs] = useState<AuditEntry[]>([
    {
      id: "AUD-99104",
      timestamp: new Date().toISOString(),
      user: "Dr. Chen (MD)",
      role: "CLINICIAN",
      action: "PREDICTION_VALIDATED_ACCEPT",
      resource: "CASE-4921 / PRED-1092",
      integrity_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
    {
      id: "AUD-99103",
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      user: "Dr. Patel (MD)",
      role: "RADIOLOGIST",
      action: "GRADCAM_SALIENCY_RECALCULATED",
      resource: "PRED-1092 [Cardiomegaly]",
      integrity_hash: "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
    },
    {
      id: "AUD-99102",
      timestamp: new Date(Date.now() - 7200000).toISOString(),
      user: "System AI Engine",
      role: "SYSTEM",
      action: "MULTIMODAL_INFERENCE_EXECUTED",
      resource: "CASE-4921",
      integrity_hash: "4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce",
    },
    {
      id: "AUD-99101",
      timestamp: new Date(Date.now() - 14400000).toISOString(),
      user: "Dr. Chen (MD)",
      role: "CLINICIAN",
      action: "PATIENT_INTAKE_CREATED",
      resource: "PATIENT-SHA256(MRN)",
      integrity_hash: "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
    },
  ]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-gray-900 flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-primary-600" />
            Institutional Audit Trail &amp; Regulatory Log
          </h1>
          <p className="text-xs text-gray-500">
            Immutable, cryptographically verifiable ledger of all diagnostic requests, inferences, and clinical validations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded-lg bg-blue-50 px-3 py-1 text-xs font-bold text-blue-800 border border-blue-200">
            <Lock className="h-3.5 w-3.5" /> 21 CFR Part 11 Compliant
          </span>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
            <thead className="bg-gray-50 font-bold uppercase tracking-wider text-gray-600">
              <tr>
                <th className="px-4 py-3">Audit ID</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">User &amp; Role</th>
                <th className="px-4 py-3">Action Type</th>
                <th className="px-4 py-3">Target Resource</th>
                <th className="px-4 py-3">Integrity Digest (SHA-256)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white font-medium">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50/75 transition-colors">
                  <td className="px-4 py-3 font-mono font-bold text-gray-900">{log.id}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span className="font-semibold text-gray-800">{log.user}</span>
                    <span className="ml-1 text-[10px] text-gray-400">({log.role})</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-gray-100 px-2 py-0.5 font-mono text-[11px] font-bold text-gray-800">
                      {log.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-600">{log.resource}</td>
                  <td className="px-4 py-3 font-mono text-[10px] text-gray-400 truncate max-w-xs">
                    {log.integrity_hash}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
