/**
 * MedFusion AI — Clinical Review & Human-in-the-Loop Feedback API Service
 */

import api from "./api";
import type {
  ClinicalReviewCreate,
  ClinicalReviewListResponse,
  ClinicalReviewResponse,
  ClinicalReviewStatsResponse,
  ReviewDecision,
} from "../types";

export const reviewService = {
  /**
   * Submit a clinician review decision (ACCEPT, MODIFY, REJECT) with mandatory clinical notes.
   */
  async submitReview(caseId: string, payload: ClinicalReviewCreate): Promise<ClinicalReviewResponse> {
    const { data } = await api.post<ClinicalReviewResponse>(
      `/cases/${caseId}/reviews`,
      payload
    );
    return data;
  },

  /**
   * List all clinical reviews and physician decisions recorded for a diagnostic case.
   */
  async getReviewsByCase(caseId: string): Promise<ClinicalReviewListResponse> {
    const { data } = await api.get<ClinicalReviewListResponse>(
      `/cases/${caseId}/reviews`
    );
    return data;
  },

  /**
   * List all clinician feedback and reviews targeting a specific AI prediction.
   */
  async getReviewsByPrediction(predictionId: string): Promise<ClinicalReviewListResponse> {
    const { data } = await api.get<ClinicalReviewListResponse>(
      `/predictions/${predictionId}/reviews`
    );
    return data;
  },

  /**
   * Retrieve aggregate concordance metrics, modification/rejection rates, and top corrected diagnoses.
   */
  async getStatistics(reviewerId?: string): Promise<ClinicalReviewStatsResponse> {
    const { data } = await api.get<ClinicalReviewStatsResponse>("/reviews/stats", {
      params: reviewerId ? { reviewer_id: reviewerId } : undefined,
    });
    return data;
  },

  /**
   * List and filter physician reviews across cases and clinicians.
   */
  async listReviews(params?: {
    skip?: number;
    limit?: number;
    case_id?: string;
    reviewer_id?: string;
    decision?: ReviewDecision;
  }): Promise<ClinicalReviewListResponse> {
    const { data } = await api.get<ClinicalReviewListResponse>("/reviews", {
      params,
    });
    return data;
  },

  /**
   * Fetch details of a single clinical review by ID.
   */
  async getReviewById(reviewId: string): Promise<ClinicalReviewResponse> {
    const { data } = await api.get<ClinicalReviewResponse>(`/reviews/${reviewId}`);
    return data;
  },
};
