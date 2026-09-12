/**
 * MedFusion AI — Structured Tabular Clinical Records API Service
 */

import api from "./api";
import type {
  ClinicalRecord,
  ClinicalRecordCreatePayload,
  ClinicalRecordListResponse,
  ClinicalRecordWithValidationResponse,
} from "../types";

export const clinicalRecordService = {
  /**
   * Submit structured 13-parameter clinical telemetry with real-time physiological validation.
   */
  async createRecord(
    caseId: string,
    payload: ClinicalRecordCreatePayload
  ): Promise<ClinicalRecordWithValidationResponse> {
    const { data } = await api.post<ClinicalRecordWithValidationResponse>(
      `/cases/${caseId}/clinical-records`,
      payload
    );
    return data;
  },

  /**
   * Fetch a single clinical record by ID.
   */
  async getRecordById(recordId: string): Promise<ClinicalRecord> {
    const { data } = await api.get<ClinicalRecord>(`/clinical-records/${recordId}`);
    return data;
  },

  /**
   * Fetch all clinical records submitted for a diagnostic case.
   */
  async getRecordsByCase(caseId: string): Promise<ClinicalRecordListResponse> {
    const { data } = await api.get<ClinicalRecordListResponse>(
      `/cases/${caseId}/clinical-records`
    );
    return data;
  },
};
