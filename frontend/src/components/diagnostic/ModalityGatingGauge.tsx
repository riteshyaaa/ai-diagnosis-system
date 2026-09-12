/**
 * MedFusion AI — Multimodal Gating Weighting & Uncertainty Quantification Gauge
 */

import React from "react";
import { AlertTriangle, Cpu } from "lucide-react";
import { ModalityGatingDetail, UncertaintyDetail } from "../../types";

interface ModalityGatingGaugeProps {
  modalityGating?: ModalityGatingDetail | null;
  uncertainty?: UncertaintyDetail | null;
}

export const ModalityGatingGauge: React.FC<ModalityGatingGaugeProps> = ({
  modalityGating,
  uncertainty,
}) => {
  const imageWeight = modalityGating?.image_weight ?? 0.55;
  const tabularWeight = modalityGating?.tabular_weight ?? 0.45;
  const imagePercent = Math.round(imageWeight * 100);
  const tabularPercent = Math.round(tabularWeight * 100);

  const entropy = uncertainty?.entropy ?? 0.18;
  const confidenceScore = uncertainty?.confidence_score ?? 0.92;
  const crossModalConflict = uncertainty?.cross_modal_conflict ?? 0.0;
  const hasConflict =
    (uncertainty?.cross_modal_conflict !== undefined &&
      uncertainty?.cross_modal_conflict !== null &&
      uncertainty.cross_modal_conflict > 0.4) ||
    uncertainty?.abstention_recommended ||
    false;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 pb-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-1.5">
            <Cpu className="h-4 w-4 text-primary-600" />
            Multimodal Late Fusion Gating
          </h3>
          <p className="text-xs text-gray-500">
            Learned attention gating between Radiograph CNN &amp; Clinical Telemetry
          </p>
        </div>
        <span className="rounded-full bg-purple-50 px-2.5 py-0.5 text-[10px] font-bold text-purple-700">
          {modalityGating?.dominant_modality ? `Dominant: ${modalityGating.dominant_modality}` : "Softmax Fusion"}
        </span>
      </div>

      {/* Cross-Modality Conflict Alert */}
      {hasConflict && (
        <div className="mt-4 flex items-start gap-2 rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900">
          <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <strong>Cross-Modal Discrepancy Detected:</strong> Radiograph vision cues and clinical telemetry
            present divergent risk indications (Conflict index: {crossModalConflict.toFixed(2)}). Clinical human verification is strictly recommended.
          </div>
        </div>
      )}

      {/* Gating Distribution Visual Bar */}
      <div className="mt-4">
        <div className="flex justify-between text-xs font-semibold text-gray-700">
          <span className="text-primary-700">Vision Modality (DenseNet): {imagePercent}%</span>
          <span className="text-purple-700">Clinical Telemetry (MLP): {tabularPercent}%</span>
        </div>

        <div className="mt-2 flex h-3.5 w-full overflow-hidden rounded-full bg-gray-100 shadow-inner">
          <div
            className="bg-primary-600 transition-all duration-500"
            style={{ width: `${imagePercent}%` }}
            title={`Vision Weight: ${imagePercent}%`}
          />
          <div
            className="bg-purple-600 transition-all duration-500"
            style={{ width: `${tabularPercent}%` }}
            title={`Tabular Weight: ${tabularPercent}%`}
          />
        </div>

        <div className="mt-1 flex justify-between text-[10px] text-gray-400">
          <span>Imaging Features (Conv5)</span>
          <span>EHR Biomarkers (13-dim)</span>
        </div>
      </div>

      {/* Uncertainty Quantification Grid */}
      <div className="mt-5 grid grid-cols-3 gap-3 border-t border-gray-100 pt-4 text-center">
        <div className="rounded-xl bg-gray-50 p-2.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
            Predictive Entropy
          </span>
          <p className="mt-1 font-mono text-sm font-black text-gray-800">
            {entropy.toFixed(3)}
          </p>
          <span className="text-[9px] text-gray-400">Information Nats</span>
        </div>

        <div className="rounded-xl bg-gray-50 p-2.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
            Confidence Score
          </span>
          <p className="mt-1 font-mono text-sm font-black text-gray-800">
            {(confidenceScore * 100).toFixed(1)}%
          </p>
          <span className="text-[9px] text-gray-400">{uncertainty?.confidence_band || "High"}</span>
        </div>

        <div className="rounded-xl bg-gray-50 p-2.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
            Conflict Index
          </span>
          <p className="mt-1 font-mono text-sm font-black text-gray-800">
            {crossModalConflict.toFixed(3)}
          </p>
          <span className="text-[9px] text-gray-400">Cross-Modal Divergence</span>
        </div>
      </div>
    </div>
  );
};
