import React, { useState } from "react";
import { AlertTriangle, Info, X } from "lucide-react";

interface RegulatoryDisclaimerProps {
  compact?: boolean;
}

export const RegulatoryDisclaimer: React.FC<RegulatoryDisclaimerProps> = ({ compact = false }) => {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <div className={`flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 text-xs text-amber-950 ${compact ? "py-1.5" : "py-3"}`}>
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 text-amber-700" />
          <span>
            <strong>Prototype:</strong> Not clinically validated. Use synthetic data only; never use this system to guide patient care.
          </span>
        </div>
        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="flex-shrink-0 font-semibold underline hover:text-amber-700"
          aria-haspopup="dialog"
        >
          Details
        </button>
      </div>

      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setShowModal(false);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="prototype-notice-title"
            className="relative w-full max-w-lg rounded-xl border border-gray-200 bg-white p-6 shadow-2xl"
          >
            <button
              type="button"
              onClick={() => setShowModal(false)}
              className="absolute right-4 top-4 rounded p-1 text-gray-500 hover:bg-gray-100"
              aria-label="Close prototype notice"
            >
              <X className="h-5 w-5" />
            </button>
            <div className="flex items-center gap-2 text-amber-800">
              <Info className="h-5 w-5" />
              <h2 id="prototype-notice-title" className="text-base font-bold">Prototype limitations</h2>
            </div>
            <div className="mt-4 space-y-3 text-sm leading-relaxed text-gray-700">
              <p>
                This project is an engineering prototype. It has no demonstrated clinical validation and is not approved for diagnosis, triage, or treatment decisions.
              </p>
              <p>
                The current patient reference handling uses an unsalted SHA-256 digest. Hashing does not guarantee de-identification or regulatory compliance. Use synthetic identifiers and data only.
              </p>
              <p>
                Predictions, calibration, uncertainty, and explanations are available only when compatible, verified model artifacts exist. Missing artifacts must result in an explicit unavailable response.
              </p>
              <p>
                A qualified clinician must independently assess any real patient. This software is not a substitute for professional judgment.
              </p>
            </div>
            <div className="mt-6 flex justify-end">
              <button type="button" onClick={() => setShowModal(false)} className="btn-primary">
                Close
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
};
