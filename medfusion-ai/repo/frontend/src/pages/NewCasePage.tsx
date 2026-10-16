/**
 * MedFusion AI — New Diagnostic Case Creation Page
 */

import React, { useState } from "react";
import { useNavigate, Link } from "react-router";
import { FilePlus, ArrowLeft, AlertCircle, Info } from "lucide-react";
import { caseService } from "../services/cases.service";
import { patientService } from "../services/patients.service";
import { CaseModality } from "../types";
import { apiErrorMessage } from "../utils/apiError";
import { LoadingSpinner } from "../components/common/LoadingSpinner";

export const NewCasePage: React.FC = () => {
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [patientMrn, setPatientMrn] = useState("");
  const [modality, setModality] = useState<CaseModality>(CaseModality.MULTIMODAL);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chiefComplaint) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // The backend stores an unsalted SHA-256 digest of this reference.
      // This prototype must only be used with synthetic identifiers/data.
      const patient = await patientService.createPatient({
        mrn: patientMrn.trim(),
      });

      // 2. Create the clinical diagnostic case attached to this patient
      const newCase = await caseService.createCase({
        patient_id: patient.id,
        modality,
        chief_complaint: chiefComplaint,
        clinical_notes: clinicalNotes,
      });

      navigate(`/cases/${newCase.id}`);
    } catch (error: unknown) {
      setError(apiErrorMessage(error, "Failed to create diagnostic case."));
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <Link
          to="/cases"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-gray-500 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Worklist
        </Link>
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
        <div className="border-b border-gray-100 pb-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary-100 text-primary-700">
              <FilePlus className="h-5 w-5" />
            </div>
            <h1 className="text-xl font-extrabold text-gray-900">
              Initialize Diagnostic Case
            </h1>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Create a case using a synthetic patient reference. No clinical inference is run during case creation.
          </p>
        </div>

        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800">
            <AlertCircle className="h-4 w-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
              Chief Complaint / Clinical Title *
            </label>
            <input
              type="text"
              required
              value={chiefComplaint}
              onChange={(e) => setChiefComplaint(e.target.value)}
              placeholder="Enter the case title or presenting concern"
              className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3.5 py-2.5 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
                Evaluation Modality
              </label>
              <select
                value={modality}
                onChange={(e) => setModality(e.target.value as CaseModality)}
                className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3 py-2 text-xs text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
              >
                <option value={CaseModality.MULTIMODAL}>Multimodal (Fusion)</option>
                <option value={CaseModality.IMAGE_ONLY}>Image Only (Radiograph)</option>
                <option value={CaseModality.TABULAR_ONLY}>Tabular Only (Telemetry)</option>
              </select>
            </div>

          </div>

          <div>
            <label htmlFor="patient-reference" className="block text-xs font-bold uppercase tracking-wider text-gray-700">
              Synthetic patient reference *
            </label>
            <input
              id="patient-reference"
              type="text"
              required
              value={patientMrn}
              onChange={(e) => setPatientMrn(e.target.value)}
              autoComplete="off"
              placeholder="Enter a synthetic reference"
              className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3.5 py-2.5 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
            <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-amber-50 p-2 text-[11px] text-amber-900">
              <Info className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
              The server stores an unsalted SHA-256 hash of this value. Hashing alone does not establish de-identification; do not enter real patient identifiers or clinical data.
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
              Clinical Presentation &amp; Triage Notes
            </label>
            <textarea
              rows={4}
              value={clinicalNotes}
              onChange={(e) => setClinicalNotes(e.target.value)}
              placeholder="Enter patient symptoms, hemodynamic signs, duration, and clinical context..."
              className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 p-3 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-100">
            <Link
              to="/cases"
              className="rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-xs font-semibold text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-6 py-2.5 text-xs font-bold text-white shadow-md shadow-primary-600/25 hover:bg-primary-700 active:scale-95 disabled:opacity-50"
            >
              {isSubmitting ? (
                <LoadingSpinner size="sm" className="p-0 text-white" />
              ) : (
                "Create Case & Proceed to Workstation"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
