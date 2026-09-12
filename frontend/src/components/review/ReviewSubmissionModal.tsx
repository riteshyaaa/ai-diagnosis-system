/**
 * MedFusion AI — Human-in-the-Loop Clinical Review Submission Modal
 */

import React, { useState } from "react";
import { CheckCircle, Edit3, XCircle, ShieldAlert, AlertCircle } from "lucide-react";
import { Modal } from "../common/Modal";
import { ReviewDecision, ClinicalReviewCreate, ClinicalReviewResponse } from "../../types";
import { reviewService } from "../../services/reviews.service";
import { LoadingSpinner } from "../common/LoadingSpinner";

interface ReviewSubmissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  predictionId?: string | null;
  onReviewSubmitted: (review: ClinicalReviewResponse) => void;
  existingReview?: ClinicalReviewResponse | null;
}

export const ReviewSubmissionModal: React.FC<ReviewSubmissionModalProps> = ({
  isOpen,
  onClose,
  caseId,
  predictionId,
  onReviewSubmitted,
  existingReview,
}) => {
  const [decision, setDecision] = useState<ReviewDecision>(
    existingReview?.decision || ReviewDecision.ACCEPT
  );
  const [clinicalNotes, setClinicalNotes] = useState<string>(
    existingReview?.clinical_notes || ""
  );
  const [revisedDiagnosis, setRevisedDiagnosis] = useState<string>(
    existingReview?.modified_diagnosis || ""
  );
  const [revisedProbability, setRevisedProbability] = useState<number>(50);

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

    if (decision === ReviewDecision.REJECT && !clinicalNotes.trim()) {
      setError("Mandatory clinical rationale required when rejecting AI diagnostic assessment.");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: ClinicalReviewCreate = {
        prediction_id: predictionId || null,
        decision,
        clinical_notes: clinicalNotes.trim() || (decision === ReviewDecision.ACCEPT ? "Clinician accepted AI assessment." : ""),
        modified_diagnosis: decision === ReviewDecision.MODIFY ? revisedDiagnosis.trim() : null,
      };

      const review = await reviewService.submitReview(caseId, payload);
      onReviewSubmitted(review);
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to submit clinical validation review.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Physician Clinical Review & Validation"
      subtitle="Mandatory Human-in-the-Loop Supervision & Audit Trail"
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
              <span className="mt-1.5 text-xs font-bold">Accept AI Findings</span>
              <span className="text-[10px] text-gray-500 text-center">Concordant with assessment</span>
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
              <span className="mt-1.5 text-xs font-bold">Modify / Refine</span>
              <span className="text-[10px] text-gray-500 text-center">Adjust diagnosis / risk</span>
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
              <span className="text-[10px] text-gray-500 text-center">Discordant / Inaccurate</span>
            </label>
          </div>
        </div>

        {/* Conditional Fields for MODIFY */}
        {decision === ReviewDecision.MODIFY && (
          <div className="space-y-3 rounded-xl border border-amber-200 bg-amber-50/30 p-3.5 animate-in fade-in">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-amber-900">
                Revised Physician Diagnosis *
              </label>
              <input
                type="text"
                required
                value={revisedDiagnosis}
                onChange={(e) => setRevisedDiagnosis(e.target.value)}
                placeholder="e.g., Mild Cardiomegaly with Early Atelectasis"
                className="mt-1 block w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs text-gray-900 focus:border-amber-500 focus:outline-none"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs font-bold text-amber-900">
                <span>Revised Risk Estimate</span>
                <span>{revisedProbability}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={revisedProbability}
                onChange={(e) => setRevisedProbability(Number(e.target.value))}
                className="mt-1.5 h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-amber-200 accent-amber-600"
              />
            </div>
          </div>
        )}

        {/* Clinical Rationale & Notes */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
            Clinical Rationale &amp; Documentation{" "}
            {decision === ReviewDecision.REJECT && <span className="text-rose-600">*</span>}
          </label>
          <textarea
            rows={3}
            value={clinicalNotes}
            onChange={(e) => setClinicalNotes(e.target.value)}
            placeholder={
              decision === ReviewDecision.REJECT
                ? "Mandatory: Describe why the AI assessment is discordant with patient presentation..."
                : "Optional clinical commentary for patient electronic medical record..."
            }
            className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 p-3 text-xs text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
          />
        </div>

        {/* Regulatory Governance Note */}
        <div className="rounded-lg bg-blue-50/75 p-2.5 text-[11px] text-blue-900 flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-blue-600 flex-shrink-0" />
          <span>
            This submission records a tamper-evident audit record under 21 CFR Part 11 &amp; EU AI Act compliance.
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
              "Commit Physician Sign-off"
            )}
          </button>
        </div>
      </form>
    </Modal>
  );
};
