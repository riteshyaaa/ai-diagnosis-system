import React, { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3 } from "lucide-react";

import { reviewService } from "../../services/reviews.service";
import type { ClinicalReviewStatsResponse } from "../../types";
import { apiErrorMessage } from "../../utils/apiError";
import { LoadingSpinner } from "../common/LoadingSpinner";

const decisionColors = ["#10b981", "#f59e0b", "#64748b"];

export const ConcordanceDashboard: React.FC = () => {
  const [stats, setStats] = useState<ClinicalReviewStatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    reviewService
      .getStatistics()
      .then((result) => {
        if (active) setStats(result);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(
            apiErrorMessage(
              cause,
              "Could not load review statistics from the server.",
            ),
          );
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner
          size="lg"
          message="Loading recorded review statistics..."
        />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div
        role="alert"
        className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800"
      >
        {error || "Review statistics are unavailable."}
      </div>
    );
  }

  const decisionData = [
    { name: "Accepted", value: stats.accepted_count },
    { name: "Modified", value: stats.modified_count },
    { name: "Rejected", value: stats.rejected_count },
  ];
  const modifiedData = stats.top_modified_diagnoses.map((item) => ({
    diagnosis: item.diagnosis,
    count: item.count,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-black tracking-tight text-gray-900">
          <BarChart3 className="h-6 w-6 text-primary-600" />
          Recorded clinical reviews
        </h1>
        <p className="mt-1 text-xs text-gray-600">
          Descriptive counts from reviews stored in this workspace. These values
          do not establish model accuracy or clinical performance.
        </p>
      </div>

      {stats.total_reviews === 0 ? (
        <div
          role="status"
          className="rounded-2xl border border-gray-200 bg-white p-8 text-center text-sm text-gray-600"
        >
          No review decisions have been recorded.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Metric label="Review decisions" value={stats.total_reviews} />
            <Metric label="Accepted" value={stats.accepted_count} />
            <Metric label="Modified" value={stats.modified_count} />
            <Metric label="Rejected" value={stats.rejected_count} />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900">
                Recorded decision counts
              </h2>
              <div className="mt-4 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={decisionData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={60}
                      outerRadius={90}
                    >
                      {decisionData.map((entry, index) => (
                        <Cell key={entry.name} fill={decisionColors[index]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-gray-500">
                Accepted review share: {stats.concordance_rate.toFixed(1)}% of
                recorded decisions.
              </p>
            </section>

            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="text-sm font-bold text-gray-900">
                Modified diagnoses
              </h2>
              <div className="mt-4 h-64">
                {modifiedData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={modifiedData}
                      margin={{ top: 10, right: 24, left: 0, bottom: 8 }}
                    >
                      <XAxis
                        dataKey="diagnosis"
                        tick={{ fontSize: 11, fill: "#4b5563" }}
                      />
                      <YAxis
                        tick={{ fontSize: 10, fill: "#6b7280" }}
                        allowDecimals={false}
                      />
                      <Tooltip />
                      <Bar
                        dataKey="count"
                        fill="#2563eb"
                        radius={[6, 6, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-gray-500">
                    No modified diagnoses have been recorded.
                  </div>
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
};

const Metric: React.FC<{ label: string; value: number }> = ({
  label,
  value,
}) => (
  <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
    <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
      {label}
    </span>
    <p className="mt-2 text-3xl font-black text-gray-900">{value}</p>
  </div>
);
