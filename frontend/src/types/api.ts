// Minimal mirrors of components/schemas/HealthResponse and ErrorResponse in
// contracts/openapi.yaml (v1.1.1). Full OpenAPI type generation is a later
// stage; until then these shapes must be kept in sync with the contract.

export interface HealthData {
  status: "ok";
  database: "connected";
}

export interface RequestMeta {
  request_id?: string;
}

export interface HealthResponse {
  data: HealthData;
  meta?: RequestMeta;
}

export interface ErrorDetail {
  field?: string;
  reason?: string;
}

export interface ErrorInfo {
  code: string;
  message: string;
  details?: ErrorDetail[];
}

export interface ErrorResponse {
  error: ErrorInfo;
  meta?: RequestMeta;
}

// --- Authentication (Stage 2 Slice 1.5) ---
// Mirrors backend app/modules/auth/schemas.py and users/schemas.py, which
// follow API Specification §3.2. Keep in sync with contracts/openapi.yaml.

export interface UserSummary {
  id: string;
  email: string;
  display_name: string | null;
}

export interface AuthData {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: UserSummary;
}

export interface AuthResponse {
  data: AuthData;
  meta?: RequestMeta;
}

export interface UserProfileData {
  display_name: string | null;
  native_language: string;
  english_level: string | null;
  target_exam: string | null;
  target_writing_score: number | null;
  preferred_english_variant: string | null;
  preferences: Record<string, unknown>;
}

export interface MeData {
  id: string;
  email: string;
  status: string;
  email_verified_at: string | null;
  created_at: string;
  profile: UserProfileData;
}

export interface MeResponse {
  data: MeData;
  meta?: RequestMeta;
}

export interface SessionItem {
  id: string;
  device_label: string | null;
  user_agent: string | null;
  ip_address: string | null;
  created_at: string;
  last_used_at: string | null;
  expires_at: string;
  is_current: boolean;
}

export interface SessionsResponse {
  data: SessionItem[];
  meta?: RequestMeta;
}

// --- Essays (Stage 2 Slice 2A) ---
// Mirrors backend app/modules/essays/schemas.py (contract leaves essay
// response bodies open; shapes follow API Spec §2 + ERD V1.2 §6).

export type WritingType = "free_writing" | "ielts_task1" | "ielts_task2" | "other";

export interface EssayData {
  id: string;
  title: string | null;
  writing_type: WritingType;
  status: string;
  question_id: string | null;
  original_version_id: string | null;
  final_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkingDocumentSummary {
  server_revision: number;
  word_count: number;
  last_saved_at: string;
}

export interface EssayDetailData extends EssayData {
  working_document: WorkingDocumentSummary;
}

export interface EssayResponse {
  data: EssayDetailData;
  meta?: RequestMeta;
}

export interface EssayListData {
  items: EssayData[];
  next_cursor: string | null;
  limit: number;
}

export interface EssayListResponse {
  data: EssayListData;
  meta?: RequestMeta;
}
