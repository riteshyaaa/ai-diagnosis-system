import api from "./api";
import type { AuditEventListResponse } from "../types";

export interface AuditEventQuery {
  actor_id?: string;
  action?: string;
  resource_type?: string;
  start_time?: string;
  end_time?: string;
  skip?: number;
  limit?: number;
}

export const auditService = {
  async listEvents(query: AuditEventQuery = {}): Promise<AuditEventListResponse> {
    const { data } = await api.get<AuditEventListResponse>("/audit-events", {
      params: query,
    });
    return data;
  },
};
