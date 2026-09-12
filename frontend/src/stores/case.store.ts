/**
 * MedFusion AI — Diagnostic Case State Store (Zustand)
 */

import { create } from "zustand";
import { caseService } from "../services/cases.service";
import { explanationService } from "../services/explanations.service";
import { predictionService } from "../services/predictions.service";
import type {
  DiagnosticCaseDetail,
  ExplanationResponse,
  PredictionResponse,
} from "../types";

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
  runPrediction: (caseId: string, modelType?: string) => Promise<PredictionResponse>;
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
    set({ selectedCase: caseDetail });
    if (caseDetail && caseDetail.predictions && caseDetail.predictions.length > 0 && caseDetail.predictions[0]) {
      const latestPred = caseDetail.predictions[0];
      set({ activePrediction: latestPred });
      get().loadExplanationForPrediction(latestPred.id);
    } else {
      set({ activePrediction: null, activeExplanation: null });
    }
  },

  setActivePrediction: (prediction) => {
    set({ activePrediction: prediction });
    if (prediction) {
      get().loadExplanationForPrediction(prediction.id);
    } else {
      set({ activeExplanation: null });
    }
  },

  setActiveExplanation: (explanation) => set({ activeExplanation: explanation }),

  loadCase: async (caseId: string) => {
    set({ isLoading: true, error: null });
    try {
      const data = await caseService.getCaseById(caseId);
      set({ selectedCase: data, isLoading: false });

      if (data.predictions && data.predictions.length > 0 && data.predictions[0]) {
        const latestPred = data.predictions[0];
        set({ activePrediction: latestPred });
        get().loadExplanationForPrediction(latestPred.id);
      } else {
        set({ activePrediction: null, activeExplanation: null });
      }

      return data;
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Failed to load diagnostic case details.";
      set({ isLoading: false, error: msg });
      throw err;
    }
  },

  refreshCase: async (caseId: string) => {
    try {
      const data = await caseService.getCaseById(caseId);
      set({ selectedCase: data });
      if (data.predictions && data.predictions.length > 0 && data.predictions[0]) {
        const currentActiveId = get().activePrediction?.id;
        const matchingPred =
          (currentActiveId ? data.predictions.find((p) => p.id === currentActiveId) : undefined) ||
          data.predictions[0];
        if (matchingPred) {
          set({ activePrediction: matchingPred });
          get().loadExplanationForPrediction(matchingPred.id);
        }
      }
    } catch (err: any) {
      console.error("Failed to refresh case:", err);
    }
  },

  loadExplanationForPrediction: async (predictionId: string) => {
    try {
      const explanation = await explanationService.getExplanationByPredictionId(predictionId);
      set({ activeExplanation: explanation });
    } catch (err) {
      // Explanation might still be generating or unimodal
      set({ activeExplanation: null });
    }
  },

  runPrediction: async (caseId: string, modelType?: string) => {
    set({ isPredicting: true, error: null });
    try {
      const pred = await predictionService.predictCase(caseId, {
        generate_explainability: true,
        model_version: modelType,
      });
      set({ activePrediction: pred, isPredicting: false });
      if (pred) {
        get().loadExplanationForPrediction(pred.id);
      }
      return pred;
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "AI inference execution failed.";
      set({ isPredicting: false, error: msg });
      throw err;
    }
  },

  clearError: () => set({ error: null }),
}));
