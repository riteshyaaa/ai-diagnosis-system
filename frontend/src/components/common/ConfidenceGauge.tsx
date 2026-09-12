/**
 * MedFusion AI — Calibrated Confidence & Probability Gauge
 */

import React from "react";
import clsx from "clsx";
import { ConfidenceBand } from "../../types";
import { ConfidenceBandBadge } from "./Badge";

interface ConfidenceGaugeProps {
  probability: number; // 0.0 - 1.0
  calibratedProbability?: number | null;
  confidenceScore: number; // 0.0 - 1.0
  confidenceBand: ConfidenceBand | string;
  label?: string;
  size?: "sm" | "md" | "lg";
}

export const ConfidenceGauge: React.FC<ConfidenceGaugeProps> = ({
  probability,
  calibratedProbability,
  confidenceScore,
  confidenceBand,
  label = "Calibrated Risk Probability",
  size = "md",
}) => {
  const displayProb = calibratedProbability !== undefined && calibratedProbability !== null
    ? calibratedProbability
    : probability;

  const percent = Math.min(Math.max(Math.round(displayProb * 1000) / 10, 0), 100);
  const confidencePercent = Math.min(Math.max(Math.round(confidenceScore * 100), 0), 100);

  const getRiskColor = (val: number) => {
    if (val < 30) return { stroke: "#10b981", text: "text-emerald-600", bg: "bg-emerald-500" };
    if (val < 60) return { stroke: "#f59e0b", text: "text-amber-600", bg: "bg-amber-500" };
    return { stroke: "#ef4444", text: "text-rose-600", bg: "bg-rose-500" };
  };

  const riskTheme = getRiskColor(percent);

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          {label}
        </span>
        <ConfidenceBandBadge band={confidenceBand} />
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <div className="flex items-baseline gap-2">
          <span className={clsx("font-extrabold tracking-tight", riskTheme.text, size === "lg" ? "text-4xl" : "text-3xl")}>
            {percent}%
          </span>
          {calibratedProbability !== undefined && calibratedProbability !== null && (
            <span className="text-xs text-gray-400" title={`Raw model output: ${(probability * 100).toFixed(1)}%`}>
              (Raw: {(probability * 100).toFixed(1)}%)
            </span>
          )}
        </div>
        <div className="text-right">
          <span className="text-xs text-gray-500">Confidence Metric</span>
          <p className="text-xs font-bold text-gray-700">{confidencePercent}%</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          className={clsx("h-full transition-all duration-500 ease-out", riskTheme.bg)}
          style={{ width: `${percent}%` }}
        />
      </div>

      <div className="mt-2 flex justify-between text-[10px] text-gray-400">
        <span>0% (Low Risk)</span>
        <span>50% (Threshold)</span>
        <span>100% (High Risk)</span>
      </div>
    </div>
  );
};
