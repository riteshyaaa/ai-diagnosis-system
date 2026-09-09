/**
 * MedFusion AI — TypeScript Type Definitions
 *
 * Central type definitions for the frontend application.
 * Types will be expanded as modules are implemented.
 */

// --- Enums ---

export enum UserRole {
  ADMIN = "admin",
  DOCTOR = "doctor",
  RESEARCHER = "researcher",
}

export enum PredictionStatus {
  QUEUED = "queued",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum ReviewDecision {
  APPROVED = "approved",
  MODIFIED = "modified",
  REJECTED = "rejected",
}

export enum ConfidenceBand {
  HIGH = "high",
  MODERATE = "moderate",
  LOW = "low",
}

export enum ClinicalValueStatus {
  NORMAL = "normal",
  ABNORMAL = "abnormal",
  MISSING = "missing",
  OUTLIER = "outlier",
}

// --- Auth ---

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

// --- API Response ---

export interface ApiError {
  detail: string;
  status_code: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
