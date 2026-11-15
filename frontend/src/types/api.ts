// Minimal mirrors of components/schemas/HealthResponse and ErrorResponse in
// contracts/openapi.yaml (v1.1.1). Closed contract schemas are GENERATED into
// ./generated.ts (npm run generate:api) and re-exported below; response bodies
// the contract leaves open are hand-mirrored here and kept in sync. Grammar
// shapes are hand-mirrored from the backend schemas (richer than the
// contract's open descriptions) and take precedence over generated names.

export type {
  EvaluationCreate,
  GrammarIssue,
  RewriteAccept,
  SnapshotCreate,
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
  question_prompt: string | null;
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

// --- Writing sessions (Stage 2 Slice 2D) ---
// Mirrors backend app/modules/writing_sessions/schemas.py (API Spec §5).

export type WritingMode = "assisted" | "independent";
export type ActivityType = "free_writing" | "practice" | "mock_exam";

export interface ExamConfig {
  exam_type: string;
  task_type: "task1" | "task2";
  duration_minutes: number;
  word_limit?: number | null;
}

export interface EnabledFeatures {
  realtime_grammar: boolean;
  llm_assistance: boolean;
  chinese_to_english: boolean;
  expression_recommendations: boolean;
  ghost_text: boolean;
  paragraph_analysis: boolean;
  autosave: boolean;
  post_submission_evaluation: boolean;
}

export interface SessionData {
  id: string;
  essay_id: string;
  mode: WritingMode;
  activity_type: ActivityType;
  exam_config: ExamConfig | null;
  started_at: string;
  deadline_at: string | null;
  submitted_at: string | null;
  status: "active" | "submitted" | "cancelled";
  created_at: string;
  enabled_features: EnabledFeatures;
}

export interface SessionResponse {
  data: SessionData;
  meta?: RequestMeta;
}

export interface SessionListResponse {
  data: { items: SessionData[] };
  meta?: RequestMeta;
}

export interface CreateSessionRequest {
  mode: WritingMode;
  activity_type: ActivityType;
  exam_config?: ExamConfig | null;
}

export interface SubmitSessionRequest {
  expected_server_revision: number;
}

export interface SubmitData {
  session_id: string;
  status: string;
  submitted_at: string;
  final_version_id: string;
  server_revision: number;
  shared_original: boolean;
}

export interface SubmitResponse {
  data: SubmitData;
  meta?: RequestMeta;
}

// --- Grammar (Stage 2 Slice 3) ---
// Mirrors backend app/modules/grammar/schemas.py + contract GrammarIssue.

export type IssueCategory =
  | "grammar"
  | "spelling"
  | "vocabulary"
  | "collocation"
  | "naturalness"
  | "style";

export interface SuggestionStub {
  id: string;
  display_text: string;
  answer_revealed: boolean;
}

export interface IssueData {
  id: string;
  category: IssueCategory;
  sub_category: string | null;
  source: "rule_engine" | "llm" | "hybrid";
  rule_id: string | null;
  severity: "high" | "medium" | "low";
  source_server_revision: number;
  essay_version_id: string | null;
  start_offset: number;
  end_offset: number;
  offset_unit: "unicode_codepoint";
  anchor_text: string;
  short_explanation: string | null;
  status: "detected" | "resolved" | "ignored" | "stale";
  suggestions: SuggestionStub[];
}

export interface GrammarCheckRequest {
  session_id: string;
  server_revision: number;
  client_revision: number;
  text: string;
  text_range: { start: number; end: number; offset_unit: "unicode_codepoint" };
  context?: { previous_sentence?: string | null; next_sentence?: string | null; paragraph_text?: string | null };
}

export interface GrammarCheckData {
  server_revision: number;
  client_revision: number;
  check_status: "completed" | "partial";
  issues: IssueData[];
}

export interface GrammarCheckResponse {
  data: GrammarCheckData;
  meta?: RequestMeta;
}

export interface IssueListResponse {
  data: { items: IssueData[] };
  meta?: RequestMeta;
}

export interface IssueResponse {
  data: IssueData;
  meta?: RequestMeta;
}

export interface RevealedSuggestion {
  id: string;
  suggested_text: string;
  explanation: string | null;
  is_recommended: boolean;
}

export interface RevealResponse {
  data: { issue_id: string; suggestions: RevealedSuggestion[] };
  meta?: RequestMeta;
}

export interface IssueValidationRequest {
  issue_id: string;
  base_revision: number;
  client_revision: number;
  content_json: TipTapDocument;
  plain_text?: string;
  word_count?: number;
  modified_range: { start: number; end: number; offset_unit: "unicode_codepoint" };
}

export interface IssueValidationData {
  issue_id: string;
  validation_status: "correct" | "incorrect" | "needs_review";
  is_resolved: boolean;
  server_revision: number;
}

export interface IssueValidationResponse {
  data: IssueValidationData;
  meta?: RequestMeta;
}

export interface TeachingRequest {
  server_revision: number;
  client_revision: number;
  current_sentence: string;
  paragraph_context?: string | null;
  user_current_text?: string | null;
}

export interface TeachingData {
  teaching_id: string;
  issue_id: string;
  source_server_revision: number;
  title: string;
  why_wrong: string;
  grammar_rule: string;
  recommended_correction: string;
  personalized_note: string | null;
}

export interface TeachingResponse {
  data: TeachingData;
  meta?: RequestMeta;
}

export interface AcceptIssueRequest {
  base_revision: number;
  client_revision: number;
  suggestion_id?: string | null;
}

export interface AcceptIssueData {
  issue_id: string;
  suggestion_id: string;
  server_revision: number;
  applied_text: string;
  content_json: TipTapDocument;
  plain_text: string;
  word_count: number;
}

export interface AcceptIssueResponse {
  data: AcceptIssueData;
  meta?: RequestMeta;
}

// --- Expressions (Stage 2 Slice 4) ---
// Mirrors backend app/modules/expressions/schemas.py (API Spec §8–9).

export interface ExpressionData {
  id: string;
  english_text: string;
  chinese_meaning: string | null;
  original_text: string | null;
  learning_value_reason: string | null;
  usage_context: string | null;
  topic: string | null;
  register: string | null;
  grammar_pattern: string | null;
  tags: string[];
  status: "collected" | "learning" | "reviewing" | "mastered" | "archived";
  created_at: string;
  updated_at: string;
}

export interface ExpressionResponse {
  data: ExpressionData;
  meta?: RequestMeta;
}

export interface ExpressionListResponse {
  data: { items: ExpressionData[]; next_cursor: string | null; limit: number };
  meta?: RequestMeta;
}

export interface CreateExpressionRequest {
  english_text: string;
  chinese_meaning?: string | null;
  original_text?: string | null;
  learning_value_reason?: string | null;
  usage_context?: string | null;
  topic?: string | null;
  register?: string | null;
  grammar_pattern?: string | null;
  tags?: string[];
  source_type?: "translation" | "correction" | "suggestion" | "essay" | "manual";
  essay_id?: string | null;
  source_context?: string | null;
}

export interface PolishRequest {
  session_id: string;
  server_revision: number;
  client_revision: number;
  selected_text: string;
  sentence: string;
  paragraph_context?: string | null;
  max_suggestions?: number;
}

export interface TranslationRequest {
  session_id: string;
  server_revision: number;
  client_revision: number;
  chinese_text: string;
  sentence_context: string;
  paragraph_context?: string | null;
}

export interface SuggestionItemData {
  id: string;
  english_text: string;
  chinese_meaning: string | null;
  usage_note: string | null;
  register: string | null;
  source: "llm" | "previously_learned";
  expression_id: string | null;
  previously_learned: boolean;
  status: string;
}

export interface SuggestionData {
  id: string;
  essay_id: string;
  kind: "polish" | "translation";
  selected_text: string;
  server_revision: number;
  status: string;
  created_at: string;
  items: SuggestionItemData[];
}

export interface SuggestionResponse {
  data: SuggestionData;
  meta?: RequestMeta;
}

export interface AcceptExpressionSuggestionRequest {
  item_id: string;
  base_revision: number;
  client_revision: number;
  content_json: TipTapDocument;
  plain_text?: string;
  word_count?: number;
  modified_range: { start: number; end: number; offset_unit: "unicode_codepoint" };
}

export interface AcceptExpressionSuggestionData {
  suggestion_id: string;
  item_id: string;
  server_revision: number;
  content_json: TipTapDocument;
  plain_text: string;
  word_count: number;
}

export interface AcceptExpressionSuggestionResponse {
  data: AcceptExpressionSuggestionData;
  meta?: RequestMeta;
}
