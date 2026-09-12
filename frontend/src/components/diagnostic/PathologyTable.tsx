/**
 * MedFusion AI — 5-Label Thoracic Pathology Breakdown Table
 */

import React from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";
import { PathologyDetail } from "../../types";

interface PathologyTableProps {
  findings: PathologyDetail[];
}

export const PathologyTable: React.FC<PathologyTableProps> = ({ findings }) => {
  if (!findings || findings.length === 0) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-6 text-center text-gray-400">
        <p className="text-xs">No multi-label thoracic pathology findings available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 pb-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900">
            Multi-Label Thoracic Pathology Detection
          </h3>
          <p className="text-xs text-gray-500">
            DenseNet-121 / ResNet-50 5-class multi-label sigmoidal probabilities
          </p>
        </div>
        <span className="rounded-full bg-primary-50 px-2.5 py-0.5 text-[10px] font-bold text-primary-700">
          5 Clinical Targets
        </span>
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border border-gray-100">
        <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
          <thead className="bg-gray-50 font-bold uppercase tracking-wider text-gray-600">
            <tr>
              <th className="px-4 py-3">Pathology Target</th>
              <th className="px-4 py-3">Probability</th>
              <th className="px-4 py-3">Threshold</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Severity Indicator</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {findings.map((item, idx) => {
              const percent = (item.probability * 100).toFixed(1);
              const isPositive = item.positive ?? item.probability >= (item.threshold || 0.5);
              const thresholdPercent = ((item.threshold || 0.5) * 100).toFixed(0);

              return (
                <tr key={idx} className="hover:bg-gray-50/75 transition-colors">
                  <td className="px-4 py-3 font-semibold text-gray-900">
                    {item.pathology}
                  </td>
                  <td className="px-4 py-3 font-mono font-bold text-gray-800">
                    {percent}%
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    &ge; {thresholdPercent}%
                  </td>
                  <td className="px-4 py-3">
                    {isPositive ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-bold text-rose-700 border border-rose-200">
                        <AlertCircle className="h-3 w-3" /> Positive Finding
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 border border-emerald-100">
                        <CheckCircle2 className="h-3 w-3" /> Negative / Normal
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-100">
                        <div
                          className={`h-full rounded-full ${
                            item.probability >= 0.7
                              ? "bg-rose-500"
                              : item.probability >= 0.4
                              ? "bg-amber-500"
                              : "bg-emerald-500"
                          }`}
                          style={{ width: `${Math.min(item.probability * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-400 capitalize">
                        {item.confidence_band || (item.probability >= 0.7 ? "High" : item.probability >= 0.4 ? "Moderate" : "Low")}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
