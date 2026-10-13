/**
 * Displays pathology fields returned in a stored model response.
 */

import React from "react";
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
            Model-reported pathology findings
          </h3>
            <p className="text-xs text-gray-500">
            Stored model outputs; model provenance and thresholds have not been clinically validated.
          </p>
        </div>
        <span className="rounded-full bg-primary-50 px-2.5 py-0.5 text-[10px] font-bold text-primary-700">
          {findings.length} {findings.length === 1 ? "finding" : "findings"}
        </span>
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border border-gray-100">
        <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
          <thead className="bg-gray-50 font-bold uppercase tracking-wider text-gray-600">
            <tr>
              <th className="px-4 py-3">Pathology Target</th>
              <th className="px-4 py-3">Reported output</th>
              <th className="px-4 py-3">Stored model threshold</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Model band</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {findings.map((item, idx) => {
              const percent = (item.probability * 100).toFixed(1);
              const thresholdPercent = (item.threshold * 100).toFixed(0);

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
                    <span className="inline-flex rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[11px] font-medium text-gray-700">
                      {item.positive ? "Model flag: positive" : "Model flag: negative"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 capitalize">
                    {item.confidence_band ? `Reported: ${item.confidence_band}` : "Unavailable"}
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
