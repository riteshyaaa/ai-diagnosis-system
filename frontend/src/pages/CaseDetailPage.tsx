/**
 * MedFusion AI — Diagnostic Workstation & Case Detail Page
 */

import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  FileCheck,
  FileText,
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
import { CaseReportPreviewPanel } from "../components/diagnostic/CaseReportPreviewPanel";
import { caseService } from "../services/cases.service";
import { apiErrorMessage } from "../utils/apiError";
import type { CaseReportPreview, ImageQualityReport } from "../types";

function latestRecord<T>(records: T[], getTimestamp: (record: T) => string): T | null {
  return records.reduce<T | null>((latest, record) => {
    if (!latest || Date.parse(getTimestamp(record)) > Date.parse(getTimestamp(latest))) {
      return record;
    }
    return latest;
  }, null);
}

export const CaseDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const {
    selectedCase,
    activePrediction,
    activeExplanation,
    isLoading,
    isPredicting,
    error,
    loadCase,
    runPrediction,
    clearError,
  } = useCaseStore();

  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [latestUploadQualityReport, setLatestUploadQualityReport] = useState<ImageQualityReport | null>(null);
  const [reportPreview, setReportPreview] = useState<CaseReportPreview | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      setLatestUploadQualityReport(null);
      setReportPreview(null);
      setReportError(null);
      loadCase(id).catch(console.error);
    }
  }, [id, loadCase]);

  const handleRunPrediction = async () => {
    if (!id) return;
    clearError();
    setReportPreview(null);
    try {
      await runPrediction(id);
      await loadCase(id);
    } catch {
      // The store exposes the API error in the workstation.
    }
  };

  const handleReportPreview = async () => {
    if (!id) return;
    setIsLoadingReport(true);
    setReportError(null);
    try {
      setReportPreview(await caseService.getReportPreview(id));
    } catch (requestError) {
      setReportPreview(null);
      setReportError(apiErrorMessage(requestError, "Unable to generate the report preview."));
    } finally {
      setIsLoadingReport(false);
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
          {error || "The requested clinical case ID does not exist or access is unauthorized."}
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

  const primaryImage = latestRecord(selectedCase.images, (image) => image.created_at);
  const primaryClinical = latestRecord(selectedCase.clinical_records, (record) => record.updated_at);

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
            Patient record: <span className="font-mono font-bold text-gray-700">{selectedCase.patient_id}</span> &bull;
            Created: {new Date(selectedCase.created_at).toLocaleString()}
          </p>
        </div>

        {/* Inference Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleReportPreview}
            disabled={isLoadingReport}
            className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-xs font-bold text-gray-800 hover:bg-gray-50 disabled:opacity-50"
          >
            {isLoadingReport ? <LoadingSpinner size="sm" className="p-0" /> : <FileText className="h-4 w-4" />}
            Preview report
          </button>
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
                Run model inference
              </>
            )}
          </button>
        </div>
      </div>

      {reportError && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          Could not generate the report preview: {reportError}
        </div>
      )}
      {reportPreview && (
        <CaseReportPreviewPanel report={reportPreview} onClose={() => setReportPreview(null)} />
      )}

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800"
        >
          <div className="font-semibold">Inference or case request failed</div>
          <p className="mt-1">{error}</p>
        </div>
      )}

      {!activePrediction && selectedCase.predictions.length > 0 && !isPredicting && (
        <div
          role="status"
          className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
        >
          A saved prediction exists, but its recorded input version does not match the
          current case inputs or predates input-version tracking. It is hidden to avoid
          presenting an unverified result as current.
        </div>
      )}

      {/* Case input workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Image input and any stored attribution */}
        <div className="space-y-4">
          {primaryImage ? (
            <RadiographViewer
              image={primaryImage}
              qualityReport={latestUploadQualityReport}
              visualExplanation={activeExplanation?.visual_explanation}
              predictionId={activePrediction?.id}
              availablePathologies={activePrediction?.pathology_findings.map((finding) => finding.pathology)}
            />
          ) : (
            <RadiographUploader
              caseId={selectedCase.id}
              onUploadSuccess={(_image, report) => {
                setLatestUploadQualityReport(report);
                setReportPreview(null);
                loadCase(selectedCase.id);
              }}
            />
          )}
        </div>

        {/* Structured clinical input and any stored feature attribution */}
        <div className="space-y-4">
          {activeExplanation?.tabular_explanation && (
            <ShapWaterfallChart
              tabularExplanation={activeExplanation.tabular_explanation}
            />
          )}
          <ClinicalDataForm
            caseId={selectedCase.id}
            recordId={primaryClinical?.id}
            initialData={primaryClinical || undefined}
            onSuccess={() => {
              setReportPreview(null);
              loadCase(selectedCase.id);
            }}
          />
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

      {/* Clinician review history */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-4">
          <div>
            <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-primary-600" />
              Human-in-the-Loop Clinical Supervisory Reviews ({reviews.length})
            </h3>
            <p className="text-xs text-gray-500">
              Review events recorded for this case
            </p>
          </div>

          <button
            type="button"
            onClick={() => setIsReviewModalOpen(true)}
            disabled={!activePrediction}
            title={!activePrediction ? "A current prediction is required to record a review." : undefined}
            className="rounded-xl bg-gray-900 px-4 py-2 text-xs font-bold text-white hover:bg-gray-800"
          >
            {hasReview ? "Record another review" : "Record clinician review"}
          </button>
        </div>

        <div className="mt-4">
          <ReviewHistoryList reviews={reviews} />
        </div>
      </div>

      {/* Review modal is available only for a current stored prediction. */}
      {id && activePrediction && (
        <ReviewSubmissionModal
          isOpen={isReviewModalOpen}
          onClose={() => setIsReviewModalOpen(false)}
          caseId={id}
          predictionId={activePrediction?.id}
          onReviewSubmitted={() => {
            setReportPreview(null);
            loadCase(id);
          }}
        />
      )}
    </div>
  );
};
