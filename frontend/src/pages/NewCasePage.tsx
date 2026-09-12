/**
 * MedFusion AI — New Diagnostic Case Creation Page
 */

import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { FilePlus, ArrowLeft, Shield, Sparkles, AlertCircle } from "lucide-react";
import { caseService } from "../services/cases.service";
import { patientService } from "../services/patients.service";
import { CaseModality, BiologicalSex } from "../types";
import { LoadingSpinner } from "../components/common/LoadingSpinner";

export const NewCasePage: React.FC = () => {
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [patientMrn, setPatientMrn] = useState("");
  const [modality, setModality] = useState<CaseModality>(CaseModality.MULTIMODAL);
  const [patientAge, setPatientAge] = useState<number>(58);
  const [patientSex, setPatientSex] = useState<BiologicalSex>(BiologicalSex.MALE);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chiefComplaint) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // 1. Create or register de-identified patient record
      const patient = await patientService.createPatient({
        mrn: patientMrn || `MRN-${Math.floor(100000 + Math.random() * 900000)}`,
        age: patientAge,
        sex: patientSex,
        medical_history_summary: clinicalNotes.slice(0, 200) || undefined,
      });

      // 2. Create the clinical diagnostic case attached to this patient
      const newCase = await caseService.createCase({
        patient_id: patient.id,
        modality,
        chief_complaint: chiefComplaint,
        clinical_notes: clinicalNotes,
      });

      navigate(`/cases/${newCase.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to create diagnostic case.");
      setIsSubmitting(false);
    }
  };

  const handleApplySample = () => {
    setChiefComplaint("Acute Dyspnea & Progressive Retrosternal Chest Pain");
    setClinicalNotes(
      "58-year-old patient presenting with 3-day history of exertional dyspnea, orthopnea, and bilateral lower extremity edema. Suspected cardiomegaly with congestive pulmonary effusion."
    );
    setPatientMrn("MRN-984214-CARDIAC");
    setModality(CaseModality.MULTIMODAL);
    setPatientAge(58);
    setPatientSex(BiologicalSex.MALE);
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
        <button
          type="button"
          onClick={handleApplySample}
          className="inline-flex items-center gap-1 rounded-lg border border-primary-200 bg-primary-50 px-2.5 py-1 text-xs font-bold text-primary-700 hover:bg-primary-100"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Load Clinical Template
        </button>
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
            Enrolls a clinical diagnostic encounter with automatic HIPAA SHA-256 identifier hashing
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
              placeholder="e.g., Evaluation of Exertional Dyspnea & Cardiomegaly"
              className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3.5 py-2.5 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
                Patient Age
              </label>
              <input
                type="number"
                min={1}
                max={120}
                value={patientAge}
                onChange={(e) => setPatientAge(Number(e.target.value))}
                className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3 py-2 text-xs text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
                Biological Sex
              </label>
              <select
                value={patientSex}
                onChange={(e) => setPatientSex(e.target.value as BiologicalSex)}
                className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3 py-2 text-xs text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
              >
                <option value={BiologicalSex.MALE}>Male</option>
                <option value={BiologicalSex.FEMALE}>Female</option>
                <option value={BiologicalSex.OTHER}>Other</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
              Patient Medical Record Number (MRN)
            </label>
            <input
              type="text"
              value={patientMrn}
              onChange={(e) => setPatientMrn(e.target.value)}
              placeholder="e.g., MRN-884920"
              className="mt-1 block w-full rounded-xl border border-gray-300 bg-gray-50/50 px-3.5 py-2.5 text-sm text-gray-900 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
            <p className="mt-1 text-[11px] text-gray-400 flex items-center gap-1">
              <Shield className="h-3 w-3 text-emerald-600" />
              MRN is salted and cryptographically hashed (SHA-256) on ingestion.
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
