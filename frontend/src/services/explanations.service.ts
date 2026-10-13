/**
 * MedFusion AI — Explainability (XAI) API Service
 */

import api from "./api";
import type {
  ExplanationResponse,
  FeatureAttributionsResponse,
  RecalculatePathologySaliencyRequest,
  VisualExplanationResponse,
} from "../types";

export const explanationService = {
  /** Fetch attribution artifacts actually stored for a prediction, if any. */
  async getExplanationByPredictionId(predictionId: string): Promise<ExplanationResponse> {
    const { data } = await api.get<ExplanationResponse>(
      `/predictions/${predictionId}/explanation`
    );
    return data;
  },

  /** Read visual attribution from the stored composite explanation, when present. */
  async getGradCam(predictionId: string): Promise<VisualExplanationResponse> {
    const { data } = await api.get<ExplanationResponse>(
      `/predictions/${predictionId}/explanation`
    );
    if (!data.visual_explanation) {
      throw new Error("Visual attribution is unavailable for this prediction.");
    }
    return data.visual_explanation;
  },

  /** Download a protected heatmap through the authenticated API client. */
  async downloadHeatmap(predictionId: string, signal?: AbortSignal): Promise<Blob> {
    const { data } = await api.get<Blob>(`/predictions/${predictionId}/heatmap`, {
      responseType: "blob",
      signal,
    });
    return data;
  },

  /** Fetch stored tabular attribution values, when available. */
  async getShapAttributions(predictionId: string): Promise<FeatureAttributionsResponse> {
    const { data } = await api.get<FeatureAttributionsResponse>(
      `/predictions/${predictionId}/features`
    );
    return data;
  },

  /** Request alternate visual attribution; the backend may reject it if no model is available. */
  async recalculatePathologySaliency(
    predictionId: string,
    payload: RecalculatePathologySaliencyRequest
  ): Promise<VisualExplanationResponse> {
    const { data } = await api.post<VisualExplanationResponse>(
      `/predictions/${predictionId}/explain-pathology`,
      payload
    );
    return data;
  },

};
