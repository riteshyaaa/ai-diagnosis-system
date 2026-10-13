/**
 * MedFusion AI — Diagnostic Case State Store (Zustand)
 */

import { create } from "zustand";
import { caseService } from "../services/cases.service";
import { explanationService } from "../services/explanations.service";
import { predictionService } from "../services/predictions.service";
import { apiErrorMessage } from "../utils/apiError";
import type {
  DiagnosticCaseDetail,
  ExplanationResponse,
  PredictionResponse,
} from "../types";

function latestByCreatedAt<T extends { created_at: string }>(items: T[]): T | null {
  return items.reduce<T | null>((latest, item) => {
    if (!latest || Date.parse(item.created_at) > Date.parse(latest.created_at)) {
      return item;
    }
    return latest;
  }, null);
}

export function predictionMatchesCurrentInputs(
  caseDetail: DiagnosticCaseDetail,
  prediction: PredictionResponse,
): boolean {
  const image = latestByCreatedAt(caseDetail.images);
  const clinicalRecord = latestByCreatedAt(caseDetail.clinical_records);
  const predictionClinicalUpdatedAt = prediction.clinical_record_updated_at
    ? Date.parse(prediction.clinical_record_updated_at)
    : null;
  const currentClinicalUpdatedAt = clinicalRecord
    ? Date.parse(clinicalRecord.updated_at)
    : null;

  return (
    (prediction.image_record_id ?? null) === (image?.id ?? null) &&
    (prediction.image_file_hash ?? null) === (image?.file_hash ?? null) &&
    (prediction.clinical_record_id ?? null) === (clinicalRecord?.id ?? null) &&
    predictionClinicalUpdatedAt === currentClinicalUpdatedAt
  );
}

interface CaseState {
  selectedCase: DiagnosticCaseDetail | null;
  activePrediction: PredictionResponse | null;
  activeExplanation: ExplanationResponse | null;
  isLoading: boolean;
  isPredicting: boolean;
  error: string | null;

  // Actions
  setSelectedCase: (caseDetail: DiagnosticCaseDetail | null) => void;
  setActivePrediction: (prediction: PredictionResponse | null) => void;
  setActiveExplanation: (explanation: ExplanationResponse | null) => void;
  loadCase: (caseId: string) => Promise<DiagnosticCaseDetail>;
  refreshCase: (caseId: string) => Promise<void>;
  loadExplanationForPrediction: (predictionId: string) => Promise<void>;
  runPrediction: (caseId: string) => Promise<PredictionResponse>;
  clearError: () => void;
}

export const useCaseStore = create<CaseState>((set, get) => ({
  selectedCase: null,
  activePrediction: null,
  activeExplanation: null,
  isLoading: false,
  isPredicting: false,
  error: null,

  setSelectedCase: (caseDetail) => {
    set({
      selectedCase: caseDetail,
      activePrediction: null,
      activeExplanation: null,
    });
    const latestPred = caseDetail?.predictions[0];
    if (caseDetail && latestPred && predictionMatchesCurrentInputs(caseDetail, latestPred)) {
      set({ activePrediction: latestPred });
      get().loadExplanationForPrediction(latestPred.id);
    }
  },

  setActivePrediction: (prediction) => {
    set({ activePrediction: prediction, activeExplanation: null });
    if (prediction) {
      get().loadExplanationForPrediction(prediction.id);
    } else {
      set({ activeExplanation: null });
    }
  },

  setActiveExplanation: (explanation) => set({ activeExplanation: explanation }),

  loadCase: async (caseId: string) => {
    const currentCase = get().selectedCase;
    set({
      isLoading: true,
      error: null,
      ...(currentCase?.id !== caseId
        ? { selectedCase: null, activePrediction: null, activeExplanation: null }
        : {}),
    });
    try {
      const data = await caseService.getCaseById(caseId);
      set({
        selectedCase: data,
        activePrediction: null,
        activeExplanation: null,
        isLoading: false,
      });

      const latestPred = data.predictions[0];
      if (latestPred && predictionMatchesCurrentInputs(data, latestPred)) {
        set({ activePrediction: latestPred });
        get().loadExplanationForPrediction(latestPred.id);
      }

      return data;
    } catch (error: unknown) {
      const msg = apiErrorMessage(error, "Failed to load diagnostic case details.");
      set({ isLoading: false, error: msg });
      throw error;
    }
  },

  refreshCase: async (caseId: string) => {
    try {
      const data = await caseService.getCaseById(caseId);
      set({ selectedCase: data });
      if (data.predictions.length > 0 && data.predictions[0]) {
        const currentActiveId = get().activePrediction?.id;
        const matchingPred =
          (currentActiveId ? data.predictions.find((p) => p.id === currentActiveId) : undefined) ||
          data.predictions[0];
        if (matchingPred && predictionMatchesCurrentInputs(data, matchingPred)) {
          set({ activePrediction: matchingPred });
          get().loadExplanationForPrediction(matchingPred.id);
        } else {
          set({ activePrediction: null, activeExplanation: null });
        }
      } else {
        set({ activePrediction: null, activeExplanation: null });
      }
    } catch (error: unknown) {
      set({ error: apiErrorMessage(error, "Failed to refresh diagnostic case details.") });
    }
  },

  loadExplanationForPrediction: async (predictionId: string) => {
    try {
      const explanation = await explanationService.getExplanationByPredictionId(predictionId);
      if (get().activePrediction?.id === predictionId) {
        set({ activeExplanation: explanation });
      }
    } catch {
      // Explanation might still be generating or unimodal
      if (get().activePrediction?.id === predictionId) {
        set({ activeExplanation: null });
      }
    }
  },

  runPrediction: async (caseId: string) => {
    set({ isPredicting: true, error: null });
    try {
      const pred = await predictionService.predictCase(caseId, {
        generate_explainability: true,
      });
      set({ activePrediction: pred, isPredicting: false });
      if (pred) {
        get().loadExplanationForPrediction(pred.id);
      }
      return pred;
    } catch (error: unknown) {
      const msg = apiErrorMessage(error, "AI inference execution failed.");
      set({ isPredicting: false, error: msg });
      throw error;
    }
  },

  clearError: () => set({ error: null }),
}));
