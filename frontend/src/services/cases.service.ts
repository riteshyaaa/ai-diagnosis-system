/**
 * MedFusion AI — Diagnostic Case API Service
 */

import api from "./api";
import type {
  CaseCreatePayload,
  CaseListResponse,
  CaseStatusUpdatePayload,
  CaseUpdatePayload,
  DiagnosticCase,
  DiagnosticCaseDetail,
  PaginatedQuery,
} from "../types";

export const caseService = {
  /**
   * Create a new diagnostic case for a patient.
   */
  async createCase(payload: CaseCreatePayload): Promise<DiagnosticCase> {
    const { data } = await api.post<DiagnosticCase>("/cases", payload);
    return data;
  },

  /**
   * Fetch comprehensive case details including relational graph (images, records, predictions, reviews).
   */
  async getCaseById(caseId: string): Promise<DiagnosticCaseDetail> {
    const { data } = await api.get<DiagnosticCaseDetail>(`/cases/${caseId}`);
    return data;
  },

  /**
   * List paginated diagnostic cases with optional filters.
   */
  async listCases(query?: PaginatedQuery): Promise<CaseListResponse> {
    const { data } = await api.get<CaseListResponse>("/cases", {
      params: query,
    });
    return data;
  },

  /**
   * Update clinical notes or modality of a case in DRAFT status.
   */
  async updateCase(caseId: string, payload: CaseUpdatePayload): Promise<DiagnosticCase> {
    const { data } = await api.patch<DiagnosticCase>(`/cases/${caseId}`, payload);
    return data;
  },

  /**
   * Advance or alter the case workflow status.
   */
  async updateCaseStatus(caseId: string, payload: CaseStatusUpdatePayload): Promise<DiagnosticCase> {
    const { data } = await api.put<DiagnosticCase>(`/cases/${caseId}/status`, payload);
    return data;
  },

  /**
   * Delete a case (only permissible for cases in DRAFT state).
   */
  async deleteCase(caseId: string): Promise<void> {
    await api.delete(`/cases/${caseId}`);
  },
};
