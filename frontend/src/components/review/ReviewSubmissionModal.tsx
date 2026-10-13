/**
 * MedFusion AI — Human-in-the-Loop Clinical Review Submission Modal
 */

import React, { useState } from "react";
import { CheckCircle, Edit3, XCircle, Info, AlertCircle } from "lucide-react";
import { Modal } from "../common/Modal";
import { ReviewDecision, ClinicalReviewCreate, ClinicalReviewResponse } from "../../types";
import { reviewService } from "../../services/reviews.service";
import { apiErrorMessage } from "../../utils/apiError";
import { LoadingSpinner } from "../common/LoadingSpinner";

interface ReviewSubmissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  predictionId?: string | null;
  onReviewSubmitted: (review: ClinicalReviewResponse) => void;
}

export const ReviewSubmissionModal: React.FC<ReviewSubmissionModalProps> = ({
  isOpen,
  onClose,
  caseId,
  predictionId,
  onReviewSubmitted,
}) => {
  const [decision, setDecision] = useState<ReviewDecision>(ReviewDecision.ACCEPT);
  const [clinicalNotes, setClinicalNotes] = useState<string>("");
  const [revisedDiagnosis, setRevisedDiagnosis] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (decision === ReviewDecision.MODIFY && !revisedDiagnosis.trim()) {
      setError("Please specify the modified clinical diagnosis.");
      return;
    }

    if (clinicalNotes.trim().length < 5) {
      setError("Enter at least five characters of review rationale.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: ClinicalReviewCreate = {
        prediction_id: predictionId || null,
        decision,
        clinical_notes: clinicalNotes.trim(),
        modified_diagnosis: decision === ReviewDecision.MODIFY ? revisedDiagnosis.trim() : null,
      };

      const review = await reviewService.submitReview(caseId, payload);
      onReviewSubmitted(review);
      onClose();
    } catch (error: unknown) {
      setError(apiErrorMessage(error, "Failed to submit clinical validation review."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Record Clinician Review"
      subtitle="Save a review decision and rationale for this prediction"
      maxWidth="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-start gap-2 rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800">
            <AlertCircle className="h-4 w-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Review Decision Selector */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Clinical Supervisory Decision
          </label>
          <div className="mt-2 grid grid-cols-3 gap-3">
            {/* Accept */}
            <label
              className={`flex flex-col items-center justify-center rounded-xl border p-3 cursor-pointer transition-all ${
                decision === ReviewDecision.ACCEPT
                  ? "border-emerald-500 bg-emerald-50/50 text-emerald-900 shadow-sm"
                  : "border-gray-200 bg-white hover:bg-gray-50 text-gray-700"
              }`}
            >
              <input
                type="radio"
                name="decision"
                value={ReviewDecision.ACCEPT}
                checked={decision === ReviewDecision.ACCEPT}
                onChange={() => setDecision(ReviewDecision.ACCEPT)}
                className="sr-only"
              />
              <CheckCircle className={`h-6 w-6 ${decision === ReviewDecision.ACCEPT ? "text-emerald-600" : "text-gray-400"}`} />
              <span className="mt-1.5 text-xs font-bold">Accept findings</span>
              <span className="text-[10px] text-gray-500 text-center">Record agreement</span>
            </label>

            {/* Modify */}
            <label
              className={`flex flex-col items-center justify-center rounded-xl border p-3 cursor-pointer transition-all ${
                decision === ReviewDecision.MODIFY
                  ? "border-amber-500 bg-amber-50/50 text-amber-900 shadow-sm"
                  : "border-gray-200 bg-white hover:bg-gray-50 text-gray-700"
              }`}
            >
              <input
                type="radio"
                name="decision"
                value={ReviewDecision.MODIFY}
                checked={decision === ReviewDecision.MODIFY}
                onChange={() => setDecision(ReviewDecision.MODIFY)}
                className="sr-only"
              />
              <Edit3 className={`h-6 w-6 ${decision === ReviewDecision.MODIFY ? "text-amber-600" : "text-gray-400"}`} />
              <span className="mt-1.5 text-xs font-bold">Modify findings</span>
              <span className="text-[10px] text-gray-500 text-center">Provide a revised finding</span>
            </label>

            {/* Reject */}
            <label
              className={`flex flex-col items-center justify-center rounded-xl border p-3 cursor-pointer transition-all ${
                decision === ReviewDecision.REJECT
                  ? "border-rose-500 bg-rose-50/50 text-rose-900 shadow-sm"
                  : "border-gray-200 bg-white hover:bg-gray-50 text-gray-700"
              }`}
            >
              <input
                type="radio"
                name="decision"
                value={ReviewDecision.REJECT}
                checked={decision === ReviewDecision.REJECT}
                onChange={() => setDecision(ReviewDecision.REJECT)}
                className="sr-only"
              />
              <XCircle className={`h-6 w-6 ${decision === ReviewDecision.REJECT ? "text-rose-600" : "text-gray-400"}`} />
              <span className="mt-1.5 text-xs font-bold">Reject Assessment</span>
              <span className="text-[10px] text-gray-500 text-center">Record disagreement</span>
            </label>
          </div>
        </div>

        {/* Conditional Fields for MODIFY */}
        {decision === ReviewDecision.MODIFY && (
          <div className="space-y-3 rounded-xl border border-amber-200 bg-amber-50/30 p-3.5 animate-in fade-in">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-amber-900">
                Revised finding *
              </label>
              <input
                type="text"
                required
                value={revisedDiagnosis}
                onChange={(e) => setRevisedDiagnosis(e.target.value)}
                placeholder="Enter the revised finding"
                className="mt-1 block w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs text-gray-900 focus:border-amber-500 focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Clinical Rationale & Notes */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Review rationale *
          </label>
          <textarea
            rows={3}
            value={clinicalNotes}
            onChange={(e) => setClinicalNotes(e.target.value)}
            placeholder={
              decision === ReviewDecision.REJECT || decision === ReviewDecision.MODIFY
                ? "Explain the reason for changing or rejecting the model-reported findings..."
                : "Record why you agree with the model-reported findings..."
            }
            className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 p-3 text-xs text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
          />
        </div>

        <div className="rounded-lg bg-amber-50 p-2.5 text-[11px] text-amber-950 flex items-center gap-2">
          <Info className="h-4 w-4 text-amber-700 flex-shrink-0" />
          <span>
            This stores a review record in the application. It is not a digital signature or a claim of regulatory compliance.
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-gray-200 bg-white px-4 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-xl bg-primary-600 px-5 py-2 text-xs font-bold text-white shadow-sm hover:bg-primary-700 active:scale-95 disabled:opacity-50"
          >
            {isSubmitting ? (
              <LoadingSpinner size="sm" className="p-0 text-white" />
            ) : (
              "Save review"
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
};
