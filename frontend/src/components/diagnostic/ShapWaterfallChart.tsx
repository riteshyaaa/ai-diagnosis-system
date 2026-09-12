/**
 * MedFusion AI — SHAP Feature Attribution & Waterfall Risk Driver Chart
 */

import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import { Activity, ArrowDown, ArrowUp } from "lucide-react";
import { FeatureAttributionsResponse } from "../../types";

interface ShapWaterfallChartProps {
  tabularExplanation?: FeatureAttributionsResponse | null;
}

export const ShapWaterfallChart: React.FC<ShapWaterfallChartProps> = ({
  tabularExplanation,
}) => {
  if (!tabularExplanation || !tabularExplanation.all_features || tabularExplanation.all_features.length === 0) {
    return (
      <div className="flex min-h-[260px] flex-col items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-white p-6 text-center text-gray-400">
        <Activity className="h-8 w-8 text-gray-300" />
        <p className="mt-2 text-xs font-semibold text-gray-500">
          No SHAP Attributions Available
        </p>
        <p className="text-[11px] text-gray-400">
          Clinical telemetry features will populate SHAP risk contributions once inference completes.
        </p>
      </div>
    );
  }

  const data = tabularExplanation.all_features.map((item) => ({
    name: item.display_name || item.feature_name.replace(/_/g, " ").toUpperCase(),
    value: item.feature_value !== undefined ? item.feature_value : "—",
    shap: Number(item.shap_value.toFixed(4)),
    isRiskIncreasing: item.direction === "risk_increasing" || item.shap_value >= 0,
    impactDescription: item.clinical_interpretation,
  }));

  // Sort by absolute SHAP magnitude descending
  data.sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap));

  return (
    <div className="flex flex-col rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 pb-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-1.5">
            <Activity className="h-4 w-4 text-primary-600" />
            SHAP Clinical Feature Attributions
          </h3>
          <p className="text-xs text-gray-500">
            TreeSHAP / KernelSHAP marginal risk contributions to cardiovascular prediction
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-semibold">
          <span className="flex items-center gap-1 text-rose-600">
            <span className="h-2.5 w-2.5 rounded bg-rose-500" />
            Increases Risk (+)
          </span>
          <span className="flex items-center gap-1 text-emerald-600">
            <span className="h-2.5 w-2.5 rounded bg-emerald-500" />
            Protective / Lowers Risk (-)
          </span>
        </div>
      </div>

      {/* Baseline / Output Indicator */}
      <div className="my-3 flex items-center justify-between rounded-xl bg-gray-50 px-4 py-2 text-xs font-medium text-gray-600">
        <div>
          <span className="text-gray-400">Expected Base Value: </span>
          <strong className="text-gray-800">
            {(tabularExplanation.base_value * 100).toFixed(1)}%
          </strong>
        </div>
        <div>
          <span className="text-gray-400">Predicted Score: </span>
          <strong className="text-primary-700 font-bold">
            {(tabularExplanation.predicted_risk * 100).toFixed(1)}%
          </strong>
        </div>
      </div>

      {/* Recharts Bar Chart */}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 90, bottom: 5 }}
          >
            <XAxis
              type="number"
              domain={["dataMin - 0.05", "dataMax + 0.05"]}
              tick={{ fontSize: 10, fill: "#6b7280" }}
              tickFormatter={(v) => v.toFixed(2)}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 10, fill: "#374151", fontWeight: 600 }}
              width={90}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length && payload[0]) {
                  const item = payload[0].payload;
                  return (
                    <div className="rounded-xl border border-gray-100 bg-white p-3 shadow-xl text-xs">
                      <p className="font-bold text-gray-900">{item.name}</p>
                      <p className="text-gray-500">
                        Patient Value: <span className="font-semibold text-gray-800">{item.value}</span>
                      </p>
                      <p className={item.isRiskIncreasing ? "text-rose-600 font-bold" : "text-emerald-600 font-bold"}>
                        SHAP Contribution: {item.shap > 0 ? `+${item.shap}` : item.shap}
                      </p>
                      {item.impactDescription && (
                        <p className="mt-1 text-[10px] text-gray-400 max-w-[200px]">
                          {item.impactDescription}
                        </p>
                      )}
                    </div>
                  );
                }
                return null;
              }}
            />
            <ReferenceLine x={0} stroke="#9ca3af" strokeWidth={1} />
            <Bar dataKey="shap" radius={[4, 4, 4, 4]}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.isRiskIncreasing ? "#f43f5e" : "#10b981"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Key Risk Drivers Table */}
      <div className="mt-4 border-t border-gray-100 pt-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-gray-700">
          Top Influential Factors
        </h4>
        <div className="mt-2 space-y-1.5">
          {data.slice(0, 3).map((item, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between rounded-lg bg-gray-50/75 px-3 py-1.5 text-xs"
            >
              <div className="flex items-center gap-2">
                {item.isRiskIncreasing ? (
                  <ArrowUp className="h-3.5 w-3.5 text-rose-600" />
                ) : (
                  <ArrowDown className="h-3.5 w-3.5 text-emerald-600" />
                )}
                <span className="font-semibold text-gray-800">{item.name}</span>
                <span className="text-[11px] text-gray-500">({item.value})</span>
              </div>
              <span
                className={`font-mono font-bold ${
                  item.isRiskIncreasing ? "text-rose-600" : "text-emerald-600"
                }`}
              >
                {item.shap > 0 ? `+${item.shap}` : item.shap}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
