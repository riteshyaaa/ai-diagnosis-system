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
  /**
   * Fetch full composite XAI explanation (Grad-CAM + SHAP + Modality Gating) for a prediction.
   */
  async getExplanationByPredictionId(predictionId: string): Promise<ExplanationResponse> {
    const { data } = await api.get<ExplanationResponse>(
      `/predictions/${predictionId}/explanation`
    );
    return data;
  },

  /**
   * Fetch visual Grad-CAM saliency map and bounding attention regions.
   */
  async getGradCam(predictionId: string): Promise<VisualExplanationResponse> {
    const { data } = await api.get<VisualExplanationResponse>(
      `/predictions/${predictionId}/gradcam`
    );
    return data;
  },

  /**
   * Fetch structured tabular SHAP feature attributions and risk contributions.
   */
  async getShapAttributions(predictionId: string): Promise<FeatureAttributionsResponse> {
    const { data } = await api.get<FeatureAttributionsResponse>(
      `/predictions/${predictionId}/shap`
    );
    return data;
  },

  /**
   * Recalculate Grad-CAM saliency heatmap for an alternative thoracic pathology.
   */
  async recalculatePathologySaliency(
    predictionId: string,
    payload: RecalculatePathologySaliencyRequest
  ): Promise<VisualExplanationResponse> {
    const { data } = await api.post<VisualExplanationResponse>(
      `/predictions/${predictionId}/gradcam/recalculate`,
      payload
    );
    return data;
  },

  /**
   * Get direct URL to download raw Grad-CAM heatmap artifact.
   */
  getHeatmapDownloadUrl(predictionId: string): string {
    const baseUrl = api.defaults.baseURL || "http://localhost:8000/api/v1";
    return `${baseUrl}/predictions/${predictionId}/heatmap`;
  },

  /**
   * Get direct URL to download blended radiograph overlay artifact.
   */
  getOverlayDownloadUrl(predictionId: string): string {
    const baseUrl = api.defaults.baseURL || "http://localhost:8000/api/v1";
    return `${baseUrl}/predictions/${predictionId}/overlay`;
  },
};
