/**
 * MedFusion AI — AI Prediction & Inference API Service
 */

import api from "./api";
import type {
  CasePredictRequest,
  DirectPredictRequest,
  PredictionListResponse,
  PredictionResponse,
} from "../types";

export const predictionService = {
  /**
   * Trigger multimodal/unimodal AI inference for an existing diagnostic case.
   */
  async predictCase(
    caseId: string,
    payload: CasePredictRequest = { generate_explainability: true }
  ): Promise<PredictionResponse> {
    const { data } = await api.post<PredictionResponse>(
      `/cases/${caseId}/predict`,
      payload
    );
    return data;
  },

  /**
   * Execute real-time direct inference without prior case persistence.
   */
  async directPredict(payload: DirectPredictRequest): Promise<PredictionResponse> {
    const { data } = await api.post<PredictionResponse>("/predict/direct", payload);
    return data;
  },

  /**
   * Fetch full details for an individual AI prediction record.
   */
  async getPredictionById(predictionId: string): Promise<PredictionResponse> {
    const { data } = await api.get<PredictionResponse>(`/predictions/${predictionId}`);
    return data;
  },

  /**
   * List all prediction records for a specific case.
   */
  async getPredictionsByCase(caseId: string): Promise<PredictionListResponse> {
    const { data } = await api.get<PredictionListResponse>(
      `/cases/${caseId}/predictions`
    );
    return data;
  },
};
