/** Model-reported modality contribution and uncertainty fields. */

import React from "react";
import { Cpu } from "lucide-react";
import { ModalityGatingDetail, UncertaintyDetail } from "../../types";

interface ModalityGatingGaugeProps {
  modalityGating?: ModalityGatingDetail | null;
  uncertainty?: UncertaintyDetail | null;
}

export const ModalityGatingGauge: React.FC<ModalityGatingGaugeProps> = ({
  modalityGating,
  uncertainty,
}) => {
  const imagePercent = modalityGating
    ? Math.round(modalityGating.image_weight * 100)
    : null;
  const tabularPercent = modalityGating
    ? Math.round(modalityGating.tabular_weight * 100)
    : null;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-100 pb-3">
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wider text-gray-900">
            <Cpu className="h-4 w-4 text-primary-600" />
            Model contribution and uncertainty
          </h3>
          <p className="text-xs text-gray-500">
            Values are shown only when the inference response includes them.
          </p>
        </div>
        <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[10px] font-bold text-gray-700">
          {modalityGating?.dominant_modality ?? "Gating unavailable"}
        </span>
      </div>

      {modalityGating && imagePercent !== null && tabularPercent !== null ? (
        <div className="mt-4">
          <div className="flex justify-between text-xs font-semibold text-gray-700">
            <span>Image: {imagePercent}%</span>
            <span>Clinical data: {tabularPercent}%</span>
          </div>
          <div
            className="mt-2 flex h-3.5 w-full overflow-hidden rounded-full bg-gray-100"
            aria-label="Model-reported modality contribution"
          >
            <div
              className="bg-primary-600"
              style={{ width: `${imagePercent}%` }}
            />
            <div
              className="bg-purple-600"
              style={{ width: `${tabularPercent}%` }}
            />
          </div>
        </div>
      ) : (
        <p className="mt-4 rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
          Modality contribution weights were not provided for this prediction.
        </p>
      )}

      {uncertainty ? (
        <div className="mt-5 grid grid-cols-1 gap-3 border-t border-gray-100 pt-4 text-center sm:grid-cols-3">
          <Metric label="Reported entropy" value={uncertainty.entropy.toFixed(3)} />
          <Metric
            label="Reported confidence score"
            value={`${(uncertainty.confidence_score * 100).toFixed(1)}%`}
          />
          <Metric
            label="Cross-modal conflict score"
            value={
              uncertainty.cross_modal_conflict == null
                ? "Unavailable"
                : uncertainty.cross_modal_conflict.toFixed(3)
            }
          />
          {uncertainty.abstention_recommended && (
            <p className="col-span-full rounded-lg border border-amber-200 bg-amber-50 p-3 text-left text-xs text-amber-900">
              The model response recommends abstention
              {uncertainty.abstention_reasons.length > 0
                ? `: ${uncertainty.abstention_reasons.join("; ")}`
                : "."}
            </p>
          )}
        </div>
      ) : (
        <p className="mt-5 border-t border-gray-100 pt-4 text-xs text-gray-600">
          Uncertainty values were not provided for this prediction.
        </p>
      )}
    </div>
  );
};

const Metric: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="rounded-xl bg-gray-50 p-2.5">
    <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
      {label}
    </span>
    <p className="mt-1 font-mono text-sm font-bold text-gray-800">{value}</p>
  </div>
);
