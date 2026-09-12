/**
 * MedFusion AI — Primary Prediction Overview & Diagnostic Card
 */

import React from "react";
import {
  AlertOctagon,
  Clock,
  ShieldCheck,
  CheckCircle,
  FileCheck,
} from "lucide-react";
import { PredictionResponse, PredictionStatus } from "../../types";
import { ConfidenceGauge } from "../common/ConfidenceGauge";

interface PredictionOverviewProps {
  prediction: PredictionResponse;
  onOpenReviewModal: () => void;
  hasReview?: boolean;
}

export const PredictionOverview: React.FC<PredictionOverviewProps> = ({
  prediction,
  onOpenReviewModal,
  hasReview = false,
}) => {
  const isAbstained =
    prediction.status === PredictionStatus.ABSTAINED ||
    prediction.confidence_band === "abstain";

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
              AI Diagnostic Assessment
            </span>
            <span className="rounded bg-primary-50 px-2 py-0.5 font-mono text-[10px] font-bold text-primary-700">
              {prediction.model_type} &bull; v{prediction.model_version}
            </span>
          </div>
          <h2 className="mt-1 text-xl font-extrabold text-gray-900">
            {prediction.primary_condition || "Cardiovascular & Pulmonary Evaluation"}
          </h2>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-lg bg-gray-50 px-2.5 py-1 text-xs text-gray-500">
            <Clock className="h-3.5 w-3.5" />
            <span>{prediction.inference_latency_ms.toFixed(0)} ms</span>
          </div>
          <button
            type="button"
            onClick={onOpenReviewModal}
            className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold shadow-sm transition-all active:scale-95 ${
              hasReview
                ? "bg-emerald-600 text-white hover:bg-emerald-700"
                : "bg-primary-600 text-white hover:bg-primary-700"
            }`}
          >
            {hasReview ? <CheckCircle className="h-4 w-4" /> : <FileCheck className="h-4 w-4" />}
            <span>{hasReview ? "Edit Clinical Review" : "Submit Clinical Review"}</span>
          </button>
        </div>
      </div>

      {/* Safety Abstention Banner */}
      {isAbstained && (
        <div className="mt-4 flex items-start gap-3 rounded-xl bg-rose-50 border border-rose-200 p-4 text-xs text-rose-900">
          <AlertOctagon className="h-5 w-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-bold text-rose-950">
              Safety Abstention Triggered &bull; Human Review Strictly Required
            </h4>
            <p className="mt-1 leading-relaxed">
              {prediction.abstention_reason ||
                "Model confidence fell below clinical safety thresholds or elevated cross-modality conflict was detected. Automated recommendation is withheld."}
            </p>
          </div>
        </div>
      )}

      {/* Probability and Confidence Section */}
      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        <ConfidenceGauge
          probability={prediction.raw_probability}
          calibratedProbability={prediction.calibrated_probability}
          confidenceScore={prediction.confidence_score}
          confidenceBand={prediction.confidence_band}
          label="Platt/Isotonic Calibrated Risk"
          size="lg"
        />

        <div className="flex flex-col justify-between rounded-xl border border-gray-100 bg-gray-50/50 p-4 text-xs">
          <div>
            <span className="font-bold uppercase tracking-wider text-gray-500">
              Clinical Context &amp; Governance
            </span>
            <p className="mt-2 text-gray-700 leading-relaxed">
              {prediction.clinical_disclaimer ||
                "Assistive CDSS output only. Requires licensed physician validation before clinical action or patient communication."}
            </p>
          </div>

          <div className="mt-4 flex items-center justify-between border-t border-gray-200 pt-3 text-[11px] text-gray-500">
            <span className="flex items-center gap-1">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
              Concordance Monitored
            </span>
            <span>Created: {new Date(prediction.created_at).toLocaleString()}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
