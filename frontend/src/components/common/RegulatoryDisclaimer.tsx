/**
 * MedFusion AI — CDSS Regulatory Safety Disclaimer Banner & Modal
 *
 * Enforces mandatory non-autonomous clinical decision support warnings:
 * "MedFusion AI is an assistive Clinical Decision Support System (CDSS) for licensed
 * healthcare professionals. It does not provide autonomous medical diagnosis. All predictions
 * require human-in-the-loop clinical review and validation."
 */

import React, { useState } from "react";
import { AlertTriangle, ShieldCheck, Info, X } from "lucide-react";

interface RegulatoryDisclaimerProps {
  compact?: boolean;
}

export const RegulatoryDisclaimer: React.FC<RegulatoryDisclaimerProps> = ({ compact = false }) => {
  const [showModal, setShowModal] = useState(false);

  if (compact) {
    return (
      <div className="flex items-center justify-between rounded-lg bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs text-amber-900">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0" />
          <span>
            <strong>Assistive CDSS:</strong> AI outputs are for clinical decision support only and require human clinician review.
          </span>
        </div>
        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="text-xs font-semibold text-amber-800 underline hover:text-amber-950 ml-2"
        >
          Details
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent border-l-4 border-amber-500 p-4 rounded-r-lg shadow-sm">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1 text-sm text-gray-800">
            <h4 className="font-semibold text-amber-900">Regulatory Clinical Decision Support Notice</h4>
            <p className="mt-1 text-xs text-gray-700 leading-relaxed">
              MedFusion AI is an assistive <strong>Clinical Decision Support System (CDSS)</strong> intended exclusively
              for licensed healthcare professionals. <strong>It does not provide autonomous medical diagnosis.</strong>{" "}
              All visual saliency heatmaps (Grad-CAM), feature attributions (SHAP), and risk probabilities indicate
              statistical correlations and must be reviewed and validated by a qualified physician.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-1 text-xs font-medium text-amber-800 hover:text-amber-950 underline px-2 py-1"
          >
            <Info className="h-3.5 w-3.5" />
            Compliance Info
          </button>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-in fade-in">
          <div className="relative w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl border border-gray-200">
            <button
              onClick={() => setShowModal(false)}
              className="absolute right-4 top-4 text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="flex items-center gap-2.5 text-primary-700">
              <ShieldCheck className="h-6 w-6 text-primary-600" />
              <h3 className="text-lg font-bold">Clinical Safety & Regulatory Framework</h3>
            </div>

            <div className="mt-4 space-y-3 text-xs text-gray-600 leading-relaxed">
              <div className="rounded-lg bg-blue-50 p-3 text-blue-900">
                <strong>FDA / EU AI Act Assistive CDSS Guideline:</strong>
                <p className="mt-1">
                  This system operates strictly under the Human-in-the-Loop paradigm. No automated medical decisions or
                  prescriptions may be enacted without clinician verification.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-gray-800">Privacy & De-identification</h5>
                <p>
                  Patient identifiers (MRN) are cryptographically hashed using SHA-256 upon intake. Raw Protected Health
                  Information (PHI) is never persisted or logged.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-gray-800">Explainability & Saliency</h5>
                <p>
                  Visual attention regions and SHAP risk factor attributions are exploratory artifacts designed to assist
                  radiological review. Saliency maps do not constitute definitive anatomical boundaries.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-gray-800">Uncertainty & Safety Abstention</h5>
                <p>
                  When predictive entropy is elevated or severe cross-modal conflict occurs between radiographs and clinical
                  telemetry, the system activates safety abstention to prevent overconfident erroneous assertions.
                </p>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="btn-primary"
              >
                Acknowledge & Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
