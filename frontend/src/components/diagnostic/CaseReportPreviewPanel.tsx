import React from "react";
import { FileText, X } from "lucide-react";
import type { CaseReportPreview } from "../../types";

interface CaseReportPreviewPanelProps {
  report: CaseReportPreview;
  onClose: () => void;
}

export const CaseReportPreviewPanel: React.FC<CaseReportPreviewPanelProps> = ({
  report,
  onClose,
}) => (
  <section
    aria-labelledby="report-preview-title"
    className="rounded-2xl border border-blue-200 bg-white p-5 shadow-sm"
  >
    <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-100 pb-4">
      <div>
        <div className="flex items-center gap-2 text-blue-800">
          <FileText className="h-5 w-5" aria-hidden="true" />
          <h2 id="report-preview-title" className="text-base font-bold">
            Draft report preview
          </h2>
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
            {report.status.replace(/_/g, " ")}
          </span>
        </div>
        <p className="mt-1 text-xs text-gray-600">
          {report.case_reference} · Generated {new Date(report.generated_at).toLocaleString()}
        </p>
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="Close report preview"
        className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </header>

    <div className="mt-4 grid gap-4 md:grid-cols-2">
      <div className="rounded-xl bg-gray-50 p-4">
        <h3 className="text-sm font-semibold text-gray-900">Case and patient summary</h3>
        <dl className="mt-2 space-y-1 text-sm text-gray-700">
          <div className="flex justify-between gap-2"><dt>Reference</dt><dd className="font-mono">{report.case_reference}</dd></div>
          <div className="flex justify-between gap-2"><dt>Patient age</dt><dd>{report.patient.age ?? "Not recorded"}</dd></div>
          <div className="flex justify-between gap-2"><dt>Sex</dt><dd className="capitalize">{report.patient.sex}</dd></div>
          <div className="flex justify-between gap-2"><dt>Input modality</dt><dd>{report.modality.replace(/_/g, " ")}</dd></div>
        </dl>
        <p className="mt-3 text-xs text-gray-500">
          Free-text notes and arbitrary raw metrics are excluded from this preview.
        </p>
      </div>

      <div className="rounded-xl bg-gray-50 p-4">
        <h3 className="text-sm font-semibold text-gray-900">Persisted inputs</h3>
        {report.image_input && (
          <p className="mt-2 break-all text-xs text-gray-700">
            Image: {report.image_input.image_type.replace(/_/g, " ")} · SHA-256 {report.image_input.sha256}
          </p>
        )}
        {report.clinical_input && (
          <p className="mt-2 text-xs text-gray-700">
            Clinical record updated {new Date(report.clinical_input.updated_at).toLocaleString()};
            resting BP {report.clinical_input.resting_bp_mm_hg} mm Hg, cholesterol {report.clinical_input.cholesterol_mg_dl} mg/dL,
            maximum heart rate {report.clinical_input.max_hr_bpm} bpm.
          </p>
        )}
        {!report.image_input && !report.clinical_input && (
          <p className="mt-2 text-sm text-gray-500">No persisted supported inputs are available.</p>
        )}
      </div>
    </div>

    {report.prediction && (
      <div className={`mt-4 rounded-xl border p-4 ${report.prediction.input_version_current ? "border-amber-200 bg-amber-50" : "border-rose-200 bg-rose-50"}`}>
        <h3 className="text-sm font-semibold text-gray-900">Model-reported output</h3>
        {!report.prediction.input_version_current && (
          <p role="alert" className="mt-2 text-sm font-semibold text-rose-800">
            This prediction references different or older inputs and is shown as stale history.
          </p>
        )}
        <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-gray-500">Finding</dt><dd className="font-semibold">{report.prediction.model_reported_finding}</dd></div>
          <div><dt className="text-xs text-gray-500">Stored output score</dt><dd>{report.prediction.stored_probability.toFixed(3)}</dd></div>
          <div><dt className="text-xs text-gray-500">Model version</dt><dd>{report.prediction.model_version} · {report.prediction.model_type}</dd></div>
          <div><dt className="text-xs text-gray-500">Model status</dt><dd>{report.prediction.status}</dd></div>
        </dl>
        <p className="mt-3 text-xs text-amber-950">{report.probability_notice}</p>
      </div>
    )}

    {report.review && (
      <div className="mt-4 rounded-xl border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-900">Clinician review record</h3>
        <p className="mt-1 text-sm text-gray-700">
          {report.review.decision} · reviewer {report.review.reviewer_id}
          {report.review.reviewer_role ? ` (${report.review.reviewer_role})` : ""}
        </p>
        {report.review.modified_diagnosis && <p className="mt-2 text-sm">Modified finding: {report.review.modified_diagnosis}</p>}
        <p className="mt-2 whitespace-pre-wrap text-sm text-gray-700">Rationale: {report.review.rationale}</p>
      </div>
    )}

    <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-950">
      {report.disclaimer}
    </p>
  </section>
);
