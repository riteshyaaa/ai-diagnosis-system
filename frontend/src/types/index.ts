/**
 * MedFusion AI — Complete TypeScript Type Definitions
 *
 * Provides type contracts matching the backend FastAPI Pydantic models:
 * - Authentication & RBAC User models
 * - De-identified Patient records (SHA-256 hashed MRN)
 * - Diagnostic Cases & Lifecycle Statuses
 * - Radiograph Image Metadata & Quality Metrics
 * - Tabular Clinical Records (13 standard parameters + validation flags)
 * - AI Multimodal Predictions, Gating, Uncertainty & Safety Abstention
 * - Explainable AI (Grad-CAM heatmaps, Saliency Attention Bounding Boxes, SHAP Waterfall)
 * - Human-in-the-Loop Clinician Review Decisions (Accept, Modify, Reject)
 * - Concordance Analytics & Aggregate Statistics
 */

// ==========================================
// 1. Enums
// ==========================================

export enum UserRole {
  CLINICIAN = "clinician",
  RADIOLOGIST = "radiologist",
  ADMIN = "admin",
  AUDITOR = "auditor",
}

export enum BiologicalSex {
  MALE = "male",
  FEMALE = "female",
  OTHER = "other",
  UNKNOWN = "unknown",
}

export enum CaseModality {
  MULTIMODAL = "multimodal",
  IMAGE_ONLY = "image_only",
  TABULAR_ONLY = "tabular_only",
}

export enum CaseStatus {
  DRAFT = "draft",
  SUBMITTED = "submitted",
  PROCESSING = "processing",
  COMPLETED = "completed",
  REVIEWED = "reviewed",
  ARCHIVED = "archived",
}

export enum ImageType {
  CHEST_XRAY_PA = "chest_xray_pa",
  CHEST_XRAY_AP = "chest_xray_ap",
  CHEST_CT_AXIAL = "chest_ct_axial",
  CHEST_CT_CORONAL = "chest_ct_coronal",
  OTHER = "other",
}

export enum ModelType {
  MULTIMODAL_LATE_FUSION = "multimodal_late_fusion",
  IMAGE_DENSENET = "image_densenet",
  IMAGE_RESNET = "image_resnet",
  TABULAR_XGBOOST = "tabular_xgboost",
  TABULAR_MLP = "tabular_mlp",
  TABULAR_RANDOM_FOREST = "tabular_random_forest",
}

export enum PredictionStatus {
  QUEUED = "queued",
  PROCESSING = "processing",
  COMPLETED = "completed",
  FAILED = "failed",
  ABSTAINED = "abstained",
}

export enum ConfidenceBand {
  HIGH = "high",
  MODERATE = "moderate",
  LOW = "low",
  ABSTAIN = "abstain",
}

export enum ReviewDecision {
  ACCEPT = "accept",
  MODIFY = "modify",
  REJECT = "reject",
}

export enum ThoracicPathology {
  ATELECTASIS = "Atelectasis",
  CARDIOMEGALY = "Cardiomegaly",
  EFFUSION = "Effusion",
  INFILTRATION = "Infiltration",
  MASS = "Mass",
}

// ==========================================
// 2. Authentication & User Models
// ==========================================

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  department?: string | null;
  is_active: boolean;
  is_verified: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  role?: UserRole;
  department?: string;
}

// ==========================================
// 3. Patient Models
// ==========================================

export interface Patient {
  id: string;
  mrn_hash: string;
  age?: number | null;
  sex: BiologicalSex;
  blood_group?: string | null;
  medical_history_summary?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PatientCreatePayload {
  mrn?: string;
  mrn_hash?: string;
  age?: number;
  sex?: BiologicalSex;
  blood_group?: string;
  medical_history_summary?: string;
}

export interface PatientListResponse {
  total: number;
  items: Patient[];
  skip: number;
  limit: number;
}

// ==========================================
// 4. Medical Image Models
// ==========================================

export interface ImageQualityReport {
  is_valid: boolean;
  quality_score: number;
  width: number;
  height: number;
  aspect_ratio: number;
  mean_intensity: number;
  contrast_std: number;
  sharpness_score: number;
  issues: string[];
  warnings: string[];
}

export interface ImageRecord {
  id: string;
  case_id: string;
  uploaded_by_id: string;
  original_filename: string;
  file_size_bytes: number;
  mime_type: string;
  file_hash: string;
  image_type: ImageType;
  width?: number | null;
  height?: number | null;
  channels: number;
  created_at: string;
  updated_at: string;
}

export interface ImageUploadResponse {
  image: ImageRecord;
  quality_report: ImageQualityReport;
  technical_metadata: Record<string, any>;
}

export interface ImageListResponse {
  total: number;
  items: ImageRecord[];
}

// ==========================================
// 5. Clinical Record Models (Tabular Telemetry)
// ==========================================

export interface ClinicalRecordBase {
  age: number;
  sex: number; // 1 = Male, 0 = Female
  chest_pain_type: number; // 0 = Typical Angina, 1 = Atypical Angina, 2 = Non-anginal, 3 = Asymptomatic
  resting_bp: number; // mm Hg (50 - 260)
  cholesterol: number; // mg/dl (80 - 600)
  fasting_bs: number; // 1 = >120 mg/dl, 0 = <=120 mg/dl
  resting_ecg: number; // 0 = Normal, 1 = ST-T abnormality, 2 = LV hypertrophy
  max_hr: number; // bpm (40 - 240)
  exercise_angina: number; // 1 = Yes, 0 = No
  st_depression: number; // mm (-2.0 - 8.0)
  st_slope: number; // 0 = Upsloping, 1 = Flat, 2 = Downsloping
  num_major_vessels: number; // 0 - 3
  thalassemia: number; // 1 = Normal, 2 = Fixed defect, 3 = Reversible defect
  bmi?: number | null;
  smoking_status?: "never" | "former" | "current" | null;
  raw_metrics?: Record<string, any>;
}

export interface ClinicalRecordCreatePayload extends ClinicalRecordBase {}

export interface ClinicalRecord extends ClinicalRecordBase {
  id: string;
  case_id: string;
  recorded_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface ClinicalValidationReport {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  critical_alerts: string[];
}

export interface ClinicalRecordWithValidationResponse {
  record: ClinicalRecord;
  validation_report: ClinicalValidationReport;
}

export interface ClinicalRecordListResponse {
  total: number;
  items: ClinicalRecord[];
}

// ==========================================
// 6. AI Prediction & Uncertainty Models
// ==========================================

export interface PathologyDetail {
  pathology: string;
  probability: number;
  threshold: number;
  positive: boolean;
  confidence_band: string;
  calibrated_probability?: number | null;
}

export interface TabularRiskDetail {
  raw_probability: number;
  calibrated_probability: number;
  risk_tier: string;
  confidence_band: string;
  positive: boolean;
}

export interface ModalityGatingDetail {
  image_weight: number;
  tabular_weight: number;
  dominant_modality: string;
}

export interface UncertaintyDetail {
  entropy: number;
  confidence_score: number;
  confidence_band: string;
  cross_modal_conflict?: number | null;
  abstention_recommended: boolean;
  abstention_reasons: string[];
}

export interface PredictionResponse {
  id: string;
  case_id?: string | null;
  model_type: ModelType;
  model_version: string;
  primary_condition: string;
  raw_probability: number;
  calibrated_probability: number;
  confidence_score: number;
  confidence_band: ConfidenceBand;
  status: PredictionStatus;
  abstention_reason?: string | null;
  detailed_predictions: Record<string, any>;
  pathology_findings: PathologyDetail[];
  clinical_risk?: TabularRiskDetail | null;
  modality_gating?: ModalityGatingDetail | null;
  uncertainty: UncertaintyDetail;
  inference_latency_ms: number;
  explanation?: ExplainabilityDetail | null;
  clinical_disclaimer: string;
  created_at: string;
}

export interface CasePredictRequest {
  model_version?: string;
  generate_explainability?: boolean;
  selected_image_id?: string;
  selected_clinical_record_id?: string;
}

export interface DirectPredictRequest {
  patient_mrn?: string;
  tabular_features?: Record<string, any>;
  generate_explainability?: boolean;
  model_version?: string;
}

export interface PredictionListResponse {
  total: number;
  items: PredictionResponse[];
}

// ==========================================
// 7. Explainability (XAI) Models
// ==========================================

export interface FeatureAttributionItem {
  feature_name: string;
  display_name: string;
  feature_value?: any;
  baseline_reference?: string | null;
  shap_value: number;
  importance_rank: number;
  direction: "risk_increasing" | "risk_decreasing";
  percentage_impact: number;
  clinical_interpretation?: string | null;
}

export interface FeatureAttributionsResponse {
  prediction_id: string;
  case_id?: string | null;
  model_type: string;
  base_value: number;
  predicted_risk: number;
  total_features_evaluated: number;
  top_risk_increasing_features: FeatureAttributionItem[];
  top_risk_decreasing_features: FeatureAttributionItem[];
  all_features: FeatureAttributionItem[];
  summary_text?: string | null;
  clinical_disclaimer: string;
}

export interface AttentionRegion {
  box: [number, number, number, number]; // [ymin, xmin, ymax, xmax] in [0.0, 1.0]
  saliency_score: number;
  anatomical_region?: string | null;
  associated_pathology?: string | null;
}

export interface VisualExplanationResponse {
  prediction_id: string;
  case_id?: string | null;
  target_pathology: string;
  heatmap_url?: string | null;
  overlay_url?: string | null;
  overlay_base64?: string | null;
  heatmap_base64?: string | null;
  attention_regions: AttentionRegion[];
  summary_text?: string | null;
  clinical_disclaimer: string;
}

export interface ExplainabilityDetail {
  id?: string;
  explanation_type: string;
  heatmap_path?: string | null;
  heatmap_base64?: string | null;
  overlay_base64?: string | null;
  shap_values?: Record<string, number> | null;
  top_features?: Array<Record<string, any>> | null;
  summary_text?: string | null;
}

export interface ExplanationResponse {
  id: string;
  prediction_id: string;
  case_id?: string | null;
  explanation_type: string;
  model_type: string;
  primary_condition: string;
  calibrated_probability: number;
  confidence_band: string;
  visual_explanation?: VisualExplanationResponse | null;
  tabular_explanation?: FeatureAttributionsResponse | null;
  modality_gating?: ModalityGatingDetail | null;
  summary_text?: string | null;
  clinical_disclaimer: string;
  created_at: string;
}

export interface RecalculatePathologySaliencyRequest {
  target_pathology: string;
  target_layer?: string | null;
}

// ==========================================
// 8. Human-in-the-Loop Clinical Review Models
// ==========================================

export interface ReviewerSummary {
  id: string;
  email: string;
  full_name: string;
  role: string;
  department?: string | null;
}

export interface ClinicalReviewCreate {
  prediction_id?: string | null;
  decision: ReviewDecision;
  modified_diagnosis?: string | null;
  clinical_notes: string;
}

export interface ClinicalReviewResponse {
  id: string;
  case_id: string;
  prediction_id?: string | null;
  reviewer_id: string;
  decision: ReviewDecision;
  modified_diagnosis?: string | null;
  clinical_notes: string;
  reviewed_at: string;
  created_at: string;
  reviewer?: ReviewerSummary | null;
  case_number?: string | null;
  ai_predicted_diagnosis?: string | null;
  concordance: boolean;
  clinical_disclaimer: string;
}

export interface ClinicalReviewListResponse {
  total: number;
  items: ClinicalReviewResponse[];
}

export interface TopModifiedDiagnosis {
  diagnosis: string;
  count: number;
}

export interface ClinicalReviewStatsResponse {
  total_reviews: number;
  accepted_count: number;
  modified_count: number;
  rejected_count: number;
  concordance_rate: number;
  modification_rate: number;
  rejection_rate: number;
  top_modified_diagnoses: TopModifiedDiagnosis[];
  recent_reviews: ClinicalReviewResponse[];
  clinical_disclaimer: string;
}

// ==========================================
// 9. Diagnostic Case Graph Models
// ==========================================

export interface CaseBase {
  modality: CaseModality;
  chief_complaint?: string | null;
  clinical_notes?: string | null;
}

export interface CaseCreatePayload extends CaseBase {
  patient_id: string;
  case_number?: string;
}

export interface CaseUpdatePayload {
  modality?: CaseModality;
  chief_complaint?: string;
  clinical_notes?: string;
}

export interface CaseStatusUpdatePayload {
  status: CaseStatus;
  reason?: string;
}

export interface DiagnosticCase extends CaseBase {
  id: string;
  case_number: string;
  patient_id: string;
  created_by_id: string;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
}

export interface DiagnosticCaseDetail extends DiagnosticCase {
  patient?: Patient | null;
  images: ImageRecord[];
  clinical_records: ClinicalRecord[];
  predictions: PredictionResponse[];
  reviews: ClinicalReviewResponse[];
}

export interface CaseListResponse {
  total: number;
  items: DiagnosticCase[];
  skip: number;
  limit: number;
}

// ==========================================
// 10. General API & UI Types
// ==========================================

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface PaginatedQuery {
  skip?: number;
  limit?: number;
  status?: CaseStatus;
  modality?: CaseModality;
  patient_id?: string;
  search?: string;
}
