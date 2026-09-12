/**
 * MedFusion AI — 13-Parameter Clinical Telemetry Ingestion Form
 */

import React, { useState } from "react";
import { Activity, AlertTriangle, Check, Sparkles } from "lucide-react";
import { clinicalRecordService } from "../../services/clinical-records.service";
import { ClinicalRecord, ClinicalRecordCreatePayload } from "../../types";
import { LoadingSpinner } from "../common/LoadingSpinner";

interface ClinicalDataFormProps {
  caseId?: string;
  onSuccess: (record: ClinicalRecord) => void;
  initialData?: Partial<ClinicalRecordCreatePayload>;
}

export const ClinicalDataForm: React.FC<ClinicalDataFormProps> = ({
  caseId,
  onSuccess,
  initialData,
}) => {
  const [formData, setFormData] = useState<ClinicalRecordCreatePayload>({
    age: initialData?.age ?? 58,
    sex: initialData?.sex ?? 1,
    chest_pain_type: initialData?.chest_pain_type ?? 2,
    resting_bp: initialData?.resting_bp ?? 140,
    cholesterol: initialData?.cholesterol ?? 245,
    fasting_bs: initialData?.fasting_bs ?? 0,
    resting_ecg: initialData?.resting_ecg ?? 1,
    max_hr: initialData?.max_hr ?? 150,
    exercise_angina: initialData?.exercise_angina ?? 0,
    st_depression: initialData?.st_depression ?? 1.5,
    st_slope: initialData?.st_slope ?? 1,
    num_major_vessels: initialData?.num_major_vessels ?? 1,
    thalassemia: initialData?.thalassemia ?? 2,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleChange = (field: keyof ClinicalRecordCreatePayload, value: number) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const applyPreset = (preset: "normal" | "elevated" | "critical") => {
    if (preset === "normal") {
      setFormData((prev) => ({
        ...prev,
        age: 42,
        sex: 0,
        chest_pain_type: 0,
        resting_bp: 118,
        cholesterol: 185,
        fasting_bs: 0,
        resting_ecg: 0,
        max_hr: 168,
        exercise_angina: 0,
        st_depression: 0.0,
        st_slope: 0,
        num_major_vessels: 0,
        thalassemia: 1,
      }));
    } else if (preset === "elevated") {
      setFormData((prev) => ({
        ...prev,
        age: 62,
        sex: 1,
        chest_pain_type: 2,
        resting_bp: 145,
        cholesterol: 260,
        fasting_bs: 1,
        resting_ecg: 1,
        max_hr: 135,
        exercise_angina: 1,
        st_depression: 2.2,
        st_slope: 1,
        num_major_vessels: 2,
        thalassemia: 2,
      }));
    } else {
      setFormData((prev) => ({
        ...prev,
        age: 71,
        sex: 1,
        chest_pain_type: 3,
        resting_bp: 175,
        cholesterol: 310,
        fasting_bs: 1,
        resting_ecg: 2,
        max_hr: 110,
        exercise_angina: 1,
        st_depression: 3.8,
        st_slope: 2,
        num_major_vessels: 3,
        thalassemia: 3,
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseId) return;
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const res = await clinicalRecordService.createRecord(caseId, formData);
      onSuccess(res.record);
    } catch (err: any) {
      setErrorMessage(err?.response?.data?.detail || "Failed to record clinical telemetry.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-gray-100 pb-3">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-1.5">
            <Activity className="h-4 w-4 text-primary-600" />
            13-Parameter Clinical Telemetry
          </h3>
          <p className="text-xs text-gray-500">
            Cardiovascular risk markers for Tabular MLP / XGBoost Late Fusion
          </p>
        </div>

        {/* Clinical Presets */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold text-gray-400 uppercase">Presets:</span>
          <button
            type="button"
            onClick={() => applyPreset("normal")}
            className="rounded-md border border-gray-200 bg-gray-50 px-2 py-0.5 text-[11px] font-medium text-gray-700 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-200"
          >
            Normal
          </button>
          <button
            type="button"
            onClick={() => applyPreset("elevated")}
            className="rounded-md border border-gray-200 bg-gray-50 px-2 py-0.5 text-[11px] font-medium text-gray-700 hover:bg-amber-50 hover:text-amber-700 hover:border-amber-200"
          >
            Elevated
          </button>
          <button
            type="button"
            onClick={() => applyPreset("critical")}
            className="rounded-md border border-gray-200 bg-gray-50 px-2 py-0.5 text-[11px] font-medium text-gray-700 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200"
          >
            High Risk
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800">
          <AlertTriangle className="h-4 w-4 text-rose-600 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Age */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Age (Years)
            </label>
            <input
              type="number"
              min={1}
              max={120}
              required
              value={formData.age}
              onChange={(e) => handleChange("age", parseInt(e.target.value) || 0)}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Sex */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Biological Sex
            </label>
            <select
              value={formData.sex}
              onChange={(e) => handleChange("sex", parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            >
              <option value={1}>Male (1)</option>
              <option value={0}>Female (0)</option>
            </select>
          </div>

          {/* Chest Pain Type */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Chest Pain Type
            </label>
            <select
              value={formData.chest_pain_type}
              onChange={(e) => handleChange("chest_pain_type", parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            >
              <option value={0}>0: Typical Angina</option>
              <option value={1}>1: Atypical Angina</option>
              <option value={2}>2: Non-anginal Pain</option>
              <option value={3}>3: Asymptomatic</option>
            </select>
          </div>

          {/* Resting BP */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Resting BP (mmHg)
            </label>
            <input
              type="number"
              min={60}
              max={250}
              required
              value={formData.resting_bp}
              onChange={(e) => handleChange("resting_bp", parseFloat(e.target.value) || 0)}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Cholesterol */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Serum Chol (mg/dl)
            </label>
            <input
              type="number"
              min={100}
              max={600}
              required
              value={formData.cholesterol}
              onChange={(e) => handleChange("cholesterol", parseFloat(e.target.value) || 0)}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Fasting Blood Sugar */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Fasting BS &gt; 120
            </label>
            <select
              value={formData.fasting_bs}
              onChange={(e) => handleChange("fasting_bs", parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            >
              <option value={0}>False (&le; 120 mg/dl)</option>
              <option value={1}>True (&gt; 120 mg/dl)</option>
            </select>
          </div>

          {/* Resting ECG */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Resting ECG
            </label>
            <select
              value={formData.resting_ecg}
              onChange={(e) => handleChange("resting_ecg", parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            >
              <option value={0}>0: Normal</option>
              <option value={1}>1: ST-T Wave Abnormality</option>
              <option value={2}>2: Left Ventricular Hypertrophy</option>
            </select>
          </div>

          {/* Max Heart Rate */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Max HR (bpm)
            </label>
            <input
              type="number"
              min={50}
              max={230}
              required
              value={formData.max_hr}
              onChange={(e) => handleChange("max_hr", parseFloat(e.target.value) || 0)}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Exercise Induced Angina */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Ex. Induced Angina
            </label>
            <select
              value={formData.exercise_angina}
              onChange={(e) => handleChange("exercise_angina", parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            >
              <option value={0}>No (0)</option>
              <option value={1}>Yes (1)</option>
            </select>
          </div>

          {/* ST Depression */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              ST Depression
            </label>
            <input
              type="number"
              step="0.1"
              min={0}
              max={10}
              required
              value={formData.st_depression}
              onChange={(e) => handleChange("st_depression", parseFloat(e.target.value) || 0)}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            />
          </div>

          {/* Slope of ST */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Slope of ST
            </label>
            <select
              value={formData.st_slope}
              onChange={(e) => handleChange("st_slope", parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            >
              <option value={0}>0: Upsloping</option>
              <option value={1}>1: Flat</option>
              <option value={2}>2: Downsloping</option>
            </select>
          </div>

          {/* Major Vessels */}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-gray-600">
              Major Vessels (0-3)
            </label>
            <select
              value={formData.num_major_vessels}
              onChange={(e) => handleChange("num_major_vessels", parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-1.5 text-xs text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
            >
              <option value={0}>0 Vessels</option>
              <option value={1}>1 Vessel</option>
              <option value={2}>2 Vessels</option>
              <option value={3}>3 Vessels</option>
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          <div className="flex items-center gap-1 text-[11px] text-gray-500">
            <Sparkles className="h-3.5 w-3.5 text-primary-500" />
            <span>Valid for both Tabular Risk MLP and Multimodal Fusion</span>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-primary-700 active:scale-95 disabled:opacity-50"
          >
            {isSubmitting ? (
              <LoadingSpinner size="sm" className="p-0 text-white" />
            ) : (
              <>
                <Check className="h-3.5 w-3.5" />
                Commit Telemetry Record
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
