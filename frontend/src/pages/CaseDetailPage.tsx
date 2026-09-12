/**
 * MedFusion AI — Diagnostic Workstation & Case Detail Page
 */

import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  FileCheck,
  Zap,
} from "lucide-react";
import { useCaseStore } from "../stores/case.store";
import { CaseStatusBadge } from "../components/common/Badge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { RadiographViewer } from "../components/diagnostic/RadiographViewer";
import { RadiographUploader } from "../components/diagnostic/RadiographUploader";
import { ClinicalDataForm } from "../components/diagnostic/ClinicalDataForm";
import { ShapWaterfallChart } from "../components/diagnostic/ShapWaterfallChart";
import { PathologyTable } from "../components/diagnostic/PathologyTable";
import { ModalityGatingGauge } from "../components/diagnostic/ModalityGatingGauge";
import { PredictionOverview } from "../components/diagnostic/PredictionOverview";
import { ReviewSubmissionModal } from "../components/review/ReviewSubmissionModal";
import { ReviewHistoryList } from "../components/review/ReviewHistoryList";
import { ModelType } from "../types";

export const CaseDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const {
    selectedCase,
    activePrediction,
    activeExplanation,
    isLoading,
    isPredicting,
    loadCase,
    runPrediction,
  } = useCaseStore();

  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState<ModelType>(
    ModelType.MULTIMODAL_LATE_FUSION
  );

  useEffect(() => {
    if (id) {
      loadCase(id).catch(console.error);
    }
  }, [id, loadCase]);

  const handleRunPrediction = async () => {
    if (!id) return;
    try {
      await runPrediction(id, selectedModel);
      await loadCase(id);
    } catch (err) {
      console.error("Inference execution failed:", err);
    }
  };

  if (isLoading && !selectedCase) {
    return (
      <div className="flex h-96 items-center justify-center">
        <LoadingSpinner size="lg" message="Loading diagnostic case workstation..." />
      </div>
    );
  }

  if (!selectedCase) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white p-8 text-center">
        <h2 className="text-lg font-bold text-gray-800">Case Not Found</h2>
        <p className="mt-1 text-xs text-gray-500">
          The requested clinical case ID does not exist or access is unauthorized.
        </p>
        <Link
          to="/cases"
          className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-primary-600 hover:underline"
        >
          <ArrowLeft className="h-4 w-4" /> Return to Worklist
        </Link>
      </div>
    );
  }

  const primaryImage =
    selectedCase.images && selectedCase.images.length > 0
      ? selectedCase.images[0]
      : null;

  const primaryClinical =
    selectedCase.clinical_records && selectedCase.clinical_records.length > 0
      ? selectedCase.clinical_records[0]
      : null;

  const reviews = selectedCase.reviews || [];
  const hasReview = reviews.length > 0;

  return (
    <div className="space-y-6">
      {/* Workstation Header */}
      <div className="flex flex-col gap-3 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link
              to="/cases"
              className="flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-gray-900"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back to Worklist
            </Link>
            <span className="text-gray-300">&bull;</span>
            <CaseStatusBadge status={selectedCase.status} />
          </div>

          <h1 className="mt-2 text-2xl font-black text-gray-900">
            {selectedCase.chief_complaint || `Case ${selectedCase.case_number || selectedCase.id.slice(0, 8)}`}
          </h1>
          <p className="mt-1 text-xs text-gray-500">
            Patient ID: <span className="font-mono font-bold text-gray-700">{selectedCase.patient_id || "ANON-SHA256"}</span> &bull;
            Created: {new Date(selectedCase.created_at).toLocaleString()}
          </p>
        </div>

        {/* Inference Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value as ModelType)}
            className="rounded-xl border border-gray-200 bg-gray-50/75 px-3 py-2 text-xs font-bold text-gray-800 focus:border-primary-500 focus:outline-none"
          >
            <option value={ModelType.MULTIMODAL_LATE_FUSION}>Multimodal Gated Late Fusion</option>
            <option value={ModelType.IMAGE_DENSENET}>Chest X-Ray DenseNet-121</option>
            <option value={ModelType.TABULAR_MLP}>Tabular Telemetry MLP</option>
          </select>

          <button
            type="button"
            onClick={handleRunPrediction}
            disabled={isPredicting}
            className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-primary-600/25 hover:bg-primary-700 active:scale-95 disabled:opacity-50 transition-all"
          >
            {isPredicting ? (
              <LoadingSpinner size="sm" className="p-0 text-white" />
            ) : (
              <>
                <Zap className="h-4 w-4" />
                Run AI Diagnostic Inference
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Multimodal Dual-Pane Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Pane: Radiograph / Grad-CAM */}
        <div className="space-y-4">
          {primaryImage ? (
            <RadiographViewer
              image={primaryImage}
              visualExplanation={activeExplanation?.visual_explanation}
              predictionId={activePrediction?.id}
            />
          ) : (
            <RadiographUploader
              caseId={selectedCase.id}
              onUploadSuccess={() => loadCase(selectedCase.id)}
            />
          )}
        </div>

        {/* Right Pane: Clinical Telemetry / SHAP Attributions */}
        <div className="space-y-4">
          {activeExplanation?.tabular_explanation ? (
            <ShapWaterfallChart
              tabularExplanation={activeExplanation.tabular_explanation}
            />
          ) : (
            <ClinicalDataForm
              caseId={selectedCase.id}
              initialData={primaryClinical || undefined}
              onSuccess={() => loadCase(selectedCase.id)}
            />
          )}
        </div>
      </div>

      {/* Primary Prediction Assessment Card */}
      {activePrediction && (
        <PredictionOverview
          prediction={activePrediction}
          onOpenReviewModal={() => setIsReviewModalOpen(true)}
          hasReview={hasReview}
        />
      )}

      {/* Multi-Label Pathology & Multimodal Gating */}
      {activePrediction && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PathologyTable findings={activePrediction.pathology_findings || []} />
          <ModalityGatingGauge
            modalityGating={activePrediction.modality_gating}
            uncertainty={activePrediction.uncertainty}
          />
        </div>
      )}

      {/* Human-in-the-Loop Clinical Supervisory Audit Section */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-4">
          <div>
            <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-primary-600" />
              Human-in-the-Loop Clinical Supervisory Reviews ({reviews.length})
            </h3>
            <p className="text-xs text-gray-500">
              Physician validation audit trail complying with non-autonomous CDSS mandates
            </p>
          </div>

          <button
            type="button"
            onClick={() => setIsReviewModalOpen(true)}
            className="rounded-xl bg-gray-900 px-4 py-2 text-xs font-bold text-white hover:bg-gray-800"
          >
            {hasReview ? "Record Additional Review" : "Sign & Validate Assessment"}
          </button>
        </div>

        <div className="mt-4">
          <ReviewHistoryList reviews={reviews} />
        </div>
      </div>

      {/* Physician Review Modal */}
      {id && (
        <ReviewSubmissionModal
          isOpen={isReviewModalOpen}
          onClose={() => setIsReviewModalOpen(false)}
          caseId={id}
          predictionId={activePrediction?.id}
          existingReview={reviews[0] || null}
          onReviewSubmitted={() => {
            loadCase(id);
          }}
        />
      )}
    </div>
  );
};
