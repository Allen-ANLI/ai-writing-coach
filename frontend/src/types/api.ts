// Minimal mirrors of components/schemas/HealthResponse and ErrorResponse in
// contracts/openapi.yaml (v1.1.1). Closed contract schemas are GENERATED into
// ./generated.ts (npm run generate:api) and re-exported below; response bodies
// the contract leaves open are hand-mirrored here and kept in sync.

export type {
  EvaluationCreate,
  GrammarCheckResponse,
  GrammarIssue,
  IssueValidationRequest,
  IssueValidationResponse,
  RewriteAccept,
  SnapshotCreate,
  TeachingRequest,
  TeachingResponse,
  TextRange,
  WorkingDocumentSaved,
  WorkingDocumentUpdate,
} from "@/types/generated";

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

// --- Working Document, snapshots, versions, restore (Stage 2 Slice 2B/2C) ---
// Mirrors backend app/modules/essays/schemas.py; request shapes follow the
// contract's WorkingDocumentUpdate / WorkingDocumentSaved / SnapshotCreate.

export interface WorkingDocumentData {
  essay_id: string;
  content_json: TipTapDocument;
  plain_text: string;
  word_count: number;
  server_revision: number;
  content_hash: string;
  last_saved_at: string;
  updated_at: string;
}

export interface WorkingDocumentResponse {
  data: WorkingDocumentData;
  meta?: RequestMeta;
}

/** Minimal TipTap/ProseMirror JSON document shape. */
export interface TipTapNode {
  type: string;
  text?: string;
  content?: TipTapNode[];
  attrs?: Record<string, unknown>;
  marks?: { type: string; attrs?: Record<string, unknown> }[];
}

export interface TipTapDocument extends TipTapNode {
  type: "doc";
}

export interface SaveWorkingDocumentRequest {
  base_revision: number;
  client_revision: number;
  content_json: TipTapDocument;
  plain_text?: string;
  word_count?: number;
}

export interface WorkingDocumentSavedData {
  essay_id: string;
  server_revision: number;
  client_revision: number;
  saved: boolean;
  saved_at: string;
}

export interface WorkingDocumentSavedResponse {
  data: WorkingDocumentSavedData;
  meta?: RequestMeta;
}

export type SnapshotVersionType = "checkpoint" | "assisted" | "final";

export interface CreateSnapshotRequest {
  source_revision: number;
  version_type: SnapshotVersionType;
  label?: string | null;
}

export interface VersionData {
  id: string;
  essay_id: string;
  version_no: number;
  version_type: string;
  label: string | null;
  word_count: number;
  source_revision: number;
  parent_version_id: string | null;
  created_by: string;
  created_at: string;
}

export interface VersionDetailData extends VersionData {
  content_json: TipTapDocument;
  plain_text: string;
  content_hash: string;
}

export interface VersionResponse {
  data: VersionDetailData;
  meta?: RequestMeta;
}

export interface VersionListData {
  items: VersionData[];
  next_cursor: string | null;
  limit: number;
}

export interface VersionListResponse {
  data: VersionListData;
  meta?: RequestMeta;
}

export interface RestoreRequest {
  version_id: string;
  base_revision: number;
}

export interface RestoreData {
  essay_id: string;
  server_revision: number;
  restored_version_id: string;
  word_count: number;
  content_hash: string;
  saved_at: string;
}

export interface RestoreResponse {
  data: RestoreData;
  meta?: RequestMeta;
}
