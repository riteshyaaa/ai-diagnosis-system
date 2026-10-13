import React, { useState } from "react";
import { Activity, AlertTriangle, Check } from "lucide-react";

import { clinicalRecordService } from "../../services/clinical-records.service";
import type {
  ClinicalRecord,
  ClinicalRecordCreatePayload,
  ClinicalRecordFormData,
} from "../../types";
import { apiErrorMessage } from "../../utils/apiError";
import { LoadingSpinner } from "../common/LoadingSpinner";

type ClinicalField =
  | "age"
  | "sex"
  | "chest_pain_type"
  | "resting_bp"
  | "cholesterol"
  | "fasting_bs"
  | "resting_ecg"
  | "max_hr"
  | "exercise_angina"
  | "st_depression"
  | "st_slope"
  | "num_major_vessels"
  | "thalassemia";

type ClinicalFormValues = Record<ClinicalField, string>;

type Choice = { value: string; label: string };
type FieldDefinition =
  | {
      key: ClinicalField;
      label: string;
      kind: "number";
      min: number;
      max: number;
      step?: number;
    }
  | { key: ClinicalField; label: string; kind: "select"; choices: Choice[] };

const fields: FieldDefinition[] = [
  { key: "age", label: "Age (years)", kind: "number", min: 1, max: 120 },
  {
    key: "sex",
    label: "Biological sex code",
    kind: "select",
    choices: [
      { value: "0", label: "0: Female" },
      { value: "1", label: "1: Male" },
    ],
  },
  {
    key: "chest_pain_type",
    label: "Chest pain type code",
    kind: "select",
    choices: [
      { value: "0", label: "0: Typical angina" },
      { value: "1", label: "1: Atypical angina" },
      { value: "2", label: "2: Non-anginal pain" },
      { value: "3", label: "3: Asymptomatic" },
    ],
  },
  { key: "resting_bp", label: "Resting blood pressure (mmHg)", kind: "number", min: 50, max: 260 },
  { key: "cholesterol", label: "Cholesterol (mg/dL)", kind: "number", min: 80, max: 600 },
  {
    key: "fasting_bs",
    label: "Fasting blood sugar over 120 mg/dL",
    kind: "select",
    choices: [
      { value: "0", label: "0: No" },
      { value: "1", label: "1: Yes" },
    ],
  },
  {
    key: "resting_ecg",
    label: "Resting ECG code",
    kind: "select",
    choices: [
      { value: "0", label: "0: Normal" },
      { value: "1", label: "1: ST-T abnormality" },
      { value: "2", label: "2: Left ventricular hypertrophy" },
    ],
  },
  { key: "max_hr", label: "Maximum heart rate (bpm)", kind: "number", min: 40, max: 240 },
  {
    key: "exercise_angina",
    label: "Exercise-induced angina",
    kind: "select",
    choices: [
      { value: "0", label: "0: No" },
      { value: "1", label: "1: Yes" },
    ],
  },
  { key: "st_depression", label: "ST depression (mm)", kind: "number", min: -2, max: 8, step: 0.1 },
  {
    key: "st_slope",
    label: "ST slope code",
    kind: "select",
    choices: [
      { value: "0", label: "0: Upsloping" },
      { value: "1", label: "1: Flat" },
      { value: "2", label: "2: Downsloping" },
    ],
  },
  {
    key: "num_major_vessels",
    label: "Major vessels (0 to 3)",
    kind: "select",
    choices: [0, 1, 2, 3].map((value) => ({
      value: String(value),
      label: String(value),
    })),
  },
  {
    key: "thalassemia",
    label: "Thalassemia code",
    kind: "select",
    choices: [
      { value: "1", label: "1: Normal" },
      { value: "2", label: "2: Fixed defect" },
      { value: "3", label: "3: Reversible defect" },
    ],
  },
];

function toFormValues(initialData?: ClinicalRecordFormData): ClinicalFormValues {
  return Object.fromEntries(
    fields.map(({ key }) => [key, initialData?.[key] == null ? "" : String(initialData[key])]),
  ) as ClinicalFormValues;
}

function toPayload(values: ClinicalFormValues): ClinicalRecordCreatePayload {
  const number = (key: ClinicalField) => Number(values[key]);
  return {
    age: number("age"),
    sex: number("sex"),
    chest_pain_type: number("chest_pain_type"),
    resting_bp: number("resting_bp"),
    cholesterol: number("cholesterol"),
    fasting_bs: number("fasting_bs"),
    resting_ecg: number("resting_ecg"),
    max_hr: number("max_hr"),
    exercise_angina: number("exercise_angina"),
    st_depression: number("st_depression"),
    st_slope: number("st_slope"),
    num_major_vessels: number("num_major_vessels"),
    thalassemia: number("thalassemia"),
  };
}

interface ClinicalDataFormProps {
  caseId?: string;
  recordId?: string;
  onSuccess: (record: ClinicalRecord) => void;
  initialData?: ClinicalRecordFormData;
}

export const ClinicalDataForm: React.FC<ClinicalDataFormProps> = ({
  caseId,
  recordId,
  onSuccess,
  initialData,
}) => {
  const [formValues, setFormValues] = useState(() => toFormValues(initialData));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!caseId) return;
    if (fields.some(({ key }) => !formValues[key].trim() || !Number.isFinite(Number(formValues[key])))) {
      setErrorMessage("Enter every required value using the source record. No values are inferred or filled in.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const payload = toPayload(formValues);
      const record = recordId
        ? await clinicalRecordService.updateRecord(recordId, payload)
        : (await clinicalRecordService.createRecord(caseId, payload)).record;
      onSuccess(record);
    } catch (error: unknown) {
      setErrorMessage(apiErrorMessage(error, "Failed to save clinical record."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="border-b border-gray-100 pb-3">
        <h3 className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wider text-gray-900">
          <Activity className="h-4 w-4 text-primary-600" />
          Structured clinical fields
        </h3>
        <p className="mt-1 text-xs text-gray-600">
          Use values from the source record. This prototype does not validate clinical interpretation or generate a diagnosis when data is saved.
        </p>
      </div>

      {errorMessage && (
        <div role="alert" className="mt-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {fields.map((field) => (
            <label key={field.key} className="block text-[11px] font-bold text-gray-700">
              {field.label}
              {field.kind === "number" ? (
                <input
                  type="number"
                  min={field.min}
                  max={field.max}
                  step={field.step ?? 1}
                  required
                  value={formValues[field.key]}
                  onChange={(event) =>
                    setFormValues((previous) => ({
                      ...previous,
                      [field.key]: event.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-2 text-xs font-normal text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
                />
              ) : (
                <select
                  required
                  value={formValues[field.key]}
                  onChange={(event) =>
                    setFormValues((previous) => ({
                      ...previous,
                      [field.key]: event.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50/50 px-2.5 py-2 text-xs font-normal text-gray-800 focus:border-primary-500 focus:bg-white focus:outline-none"
                >
                  <option value="">Select a value</option>
                  {field.choices.map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label}
                    </option>
                  ))}
                </select>
              )}
            </label>
          ))}
        </div>

        <div className="flex flex-col gap-3 border-t border-gray-100 pt-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[11px] text-gray-600">
            Schema-coded values require confirmation against the original data dictionary.
          </p>
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-primary-700 disabled:opacity-50"
          >
            {isSubmitting ? (
              <LoadingSpinner size="sm" className="p-0 text-white" />
            ) : (
              <>
                <Check className="h-3.5 w-3.5" />
                {recordId ? "Save clinical record" : "Add clinical record"}
              </>
            )}
          </button>
        </div>
      </form>
    </section>
  );
};
