/**
 * MedFusion AI — Patient API Service (De-identified privacy management)
 */

import api from "./api";
import type {
  Patient,
  PatientCreatePayload,
  PatientListResponse,
} from "../types";

export const patientService = {
  /**
   * Register a new de-identified patient (auto-hashes MRN via SHA-256).
   */
  async createPatient(payload: PatientCreatePayload): Promise<Patient> {
    const { data } = await api.post<Patient>("/patients", payload);
    return data;
  },

  /**
   * Fetch a patient record by UUID.
   */
  async getPatientById(patientId: string): Promise<Patient> {
    const { data } = await api.get<Patient>(`/patients/${patientId}`);
    return data;
  },

  /**
   * List paginated de-identified patients.
   */
  async listPatients(skip: number = 0, limit: number = 50): Promise<PatientListResponse> {
    const { data } = await api.get<PatientListResponse>("/patients", {
      params: { skip, limit },
    });
    return data;
  },
};
