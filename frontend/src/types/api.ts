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

export interface TeachingExamplePair {
  wrong: string;
  correct: string;
  note: string;
}

export interface TeachingKnowledgePoint {
  explanation: string;
  pattern: string;
  examples: TeachingExamplePair[];
}

export interface TeachingData {
  teaching_id: string;
  issue_id: string;
  source_server_revision: number;
  title: string;
  knowledge_point: TeachingKnowledgePoint;
  sentence_reason: string;
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
  exclude?: string[];
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

export interface ExtractionCandidate {
  english_text: string;
  chinese_meaning: string;
  original_text: string | null;
  learning_value_reason: string;
  usage_context: string | null;
  topic: string | null;
  grammar_pattern: string | null;
}

export interface ExtractionData {
  essay_id: string;
  version_id: string;
  extraction_scope: string;
  candidates: ExtractionCandidate[];
}

export interface ExtractionResponse {
  data: ExtractionData;
  meta?: RequestMeta;
}

// --- Learning (Stage 2 Slice 5B) ---
// Mirrors backend app/modules/learning/schemas.py (API Spec §10–11).

export interface ReviewPrompt {
  expression_id: string;
  chinese_meaning: string | null;
  topic: string | null;
  usage_context: string | null;
  status: string;
  next_review_at: string | null;
  review_count: number;
}

export interface DueReviewsResponse {
  data: { items: ReviewPrompt[]; due_count: number };
  meta?: RequestMeta;
}

export interface ReviewResultData {
  expression_id: string;
  is_correct: boolean;
  score: string;
  feedback: string | null;
  reference_expression: string;
  status: string;
  interval_days: string;
  next_review_at: string | null;
  streak_count: number;
}

export interface ReviewResultResponse {
  data: ReviewResultData;
  meta?: RequestMeta;
}

export interface ProgressData {
  expression_id: string;
  status: string;
  correct_count: number;
  incorrect_count: number;
  review_count: number;
  streak_count: number;
  interval_days: string;
  ease_factor: string | null;
  last_reviewed_at: string | null;
  next_review_at: string | null;
}

export interface ProgressResponse {
  data: ProgressData;
  meta?: RequestMeta;
}

export interface LearningSummaryData {
  total_expressions: number;
  by_status: Record<string, number>;
  due_now: number;
  reviewed_today: number;
  mastered: number;
  total_reviews: number;
}

export interface LearningSummaryResponse {
  data: LearningSummaryData;
  meta?: RequestMeta;
}

export interface WeaknessData {
  category: string;
  sub_category: string;
  total_occurrences: number;
  recent_occurrences: number;
  last_occurred_at: string | null;
  trend: string | null;
}

export interface WeaknessListResponse {
  data: { items: WeaknessData[] };
  meta?: RequestMeta;
}

// IELTS question bank (Slice 6, API Spec §12)

export interface IeltsTagRef {
  id: string;
  name: string;
  slug: string;
}

export interface IeltsQuestionSummary {
  id: string;
  task_type: "task1" | "task2";
  question_type: string | null;
  prompt_text: string;
  prompt_translation: string | null;
  difficulty: string | null;
  tags: IeltsTagRef[];
  is_favorited: boolean;
  created_at: string;
}

export interface IeltsQuestionDetail extends IeltsQuestionSummary {
  source_type: string;
  source_title: string | null;
  license_status: string;
}

export interface IeltsQuestionListResponse {
  data: { items: IeltsQuestionSummary[]; next_cursor: string | null; limit: number };
  meta?: RequestMeta;
}

export interface IeltsQuestionDetailResponse {
  data: IeltsQuestionDetail;
  meta?: RequestMeta;
}

export interface IeltsTagCount extends IeltsTagRef {
  question_count: number;
}

export interface IeltsTagListResponse {
  data: { items: IeltsTagCount[] };
  meta?: RequestMeta;
}

export interface IeltsFavoriteResponse {
  data: { question_id: string; favorited: boolean };
  meta?: RequestMeta;
}

// Evaluations & rewrites (Slice 7, API Spec §13)

export type EvaluationType = "ielts" | "general";
export type EvaluationStatus = "queued" | "processing" | "completed" | "failed" | "cancelled";
export type ModificationLevel = "level_1" | "level_2" | "level_3" | "level_4";

export interface CriterionScore {
  band: number;
  feedback: string;
}

export interface EvaluationData {
  id: string;
  essay_id: string;
  version_id: string;
  evaluation_type: EvaluationType;
  task_type: "task1" | "task2" | null;
  status: EvaluationStatus;
  overall_band: number | null;
  criteria_scores: Record<string, CriterionScore> | null;
  feedback_json: {
    overall_feedback: string;
    strengths: string[];
    improvements: string[];
  } | null;
  is_estimate: boolean;
  model_name: string | null;
  prompt_version: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface EvaluationQueuedResponse {
  data: { evaluation_id: string; status: EvaluationStatus };
  meta?: RequestMeta;
}

export interface EvaluationListResponse {
  data: { items: EvaluationData[] };
  meta?: RequestMeta;
}

export interface EvaluationResponse {
  data: EvaluationData;
  meta?: RequestMeta;
}

export interface RewriteData {
  id: string;
  evaluation_id: string;
  source_version_id: string;
  result_version_id: string | null;
  modification_level: ModificationLevel;
  status: EvaluationStatus;
  result_plain_text: string | null;
  change_summary: string | null;
  model_name: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface RewriteQueuedResponse {
  data: { rewrite_id: string; status: EvaluationStatus };
  meta?: RequestMeta;
}

export interface RewriteResponse {
  data: RewriteData;
  meta?: RequestMeta;
}

export interface AcceptRewriteResponse {
  data: {
    rewrite_id: string;
    result_version_id: string;
    server_revision: number;
    word_count: number;
  };
  meta?: RequestMeta;
}

// Outlines (Slice 8, API Spec §14)

export type OutlineStatus = "generating" | "draft" | "confirmed" | "archived" | "failed";
export type OutlineNodeType = "section" | "paragraph" | "sentence_idea";

export interface OutlineNodeData {
  id: string;
  parent_id: string | null;
  node_type: OutlineNodeType;
  title: string;
  content: string | null;
  sort_order: number;
}

export interface OutlineData {
  id: string;
  essay_id: string;
  version_no: number;
  status: OutlineStatus;
  thesis_statement: string | null;
  model_essay: string | null;
  model_essay_zh: string | null;
  outline_md: string | null;
  source_context: Record<string, unknown>;
  workflow_id: string | null;
  created_at: string;
  confirmed_at: string | null;
}

export interface OutlineDetailData extends OutlineData {
  nodes: OutlineNodeData[];
}

export interface OutlineQueuedResponse {
  data: { outline_id: string; status: OutlineStatus };
  meta?: RequestMeta;
}

export interface OutlineListResponse {
  data: { items: OutlineData[] };
  meta?: RequestMeta;
}

export interface OutlineResponse {
  data: OutlineDetailData;
  meta?: RequestMeta;
}

export interface OutlineNodeResponse {
  data: OutlineNodeData;
  meta?: RequestMeta;
}

// Conversational planner (ADR-024, contract 1.5.0)

export interface PlannerChatMessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  outline_id: string | null;
  created_at: string;
}

export interface PlannerChatResponse {
  data: { message: PlannerChatMessageData; outline: OutlineDetailData | null };
  meta?: RequestMeta;
}

export interface PlannerMessagesResponse {
  data: { items: PlannerChatMessageData[] };
  meta?: RequestMeta;
}

export interface PlannerProgressData {
  fulfilled: boolean;
  reason: string | null;
  degraded: boolean;
}

export interface PlannerProgressResponse {
  data: PlannerProgressData;
  meta?: RequestMeta;
}

// Fragment-level sentence polish (ADR-026, contract 1.7.0)

export interface PolishSentenceItem {
  id: string;
  english_text: string;
  chinese_meaning: string | null;
  usage_note: string | null;
  register: string | null;
  source: string;
  expression_id: string | null;
  previously_learned: boolean;
  start_offset: number | null;
  end_offset: number | null;
  status: string;
}

export interface PolishSentenceFragment {
  suggestion_id: string;
  anchor_text: string;
  start_offset: number;
  end_offset: number;
  note: string;
  items: PolishSentenceItem[];
}

export interface PolishSentenceResponse {
  data: { fragments: PolishSentenceFragment[] };
  meta?: RequestMeta;
}

export interface EssaySuggestionRecordItem {
  id: string;
  english_text: string;
  chinese_meaning: string | null;
  usage_note: string | null;
  status: string;
  start_offset: number | null;
  end_offset: number | null;
}

export interface EssaySuggestionRecord {
  id: string;
  kind: "polish" | "translation";
  selected_text: string;
  sentence_context: string;
  status: string;
  created_at: string;
  items: EssaySuggestionRecordItem[];
}

export interface EssaySuggestionListResponse {
  data: { items: EssaySuggestionRecord[] };
  meta?: RequestMeta;
}

// Workflows (Slice 8, API Spec §15)

export type WorkflowType = "writing_planner" | "learning_extractor" | "personalized_study_planner";
export type WorkflowStatus =
  | "running"
  | "awaiting_confirmation"
  | "completed"
  | "failed"
  | "cancelled";
export type WorkflowAction = "confirm" | "reject" | "revise" | "continue";

export interface WorkflowData {
  id: string;
  workflow_type: WorkflowType;
  essay_id: string | null;
  status: WorkflowStatus;
  current_step: string | null;
  result_json: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowQueuedResponse {
  data: { workflow_id: string; status: WorkflowStatus };
  meta?: RequestMeta;
}

export interface WorkflowResponse {
  data: WorkflowData;
  meta?: RequestMeta;
}

export interface WorkflowEventData {
  id: string;
  step: string;
  event_type: string;
  payload_json: Record<string, unknown>;
  created_at: string;
}

export interface WorkflowEventListResponse {
  data: { items: WorkflowEventData[] };
  meta?: RequestMeta;
}

export interface StudySuggestion {
  title: string;
  description: string;
  task_type: "review" | "practice" | "writing";
}

export interface StudyPlanResult {
  focus_areas: string[];
  suggestions: StudySuggestion[];
}

// Preferences (Slice 9)

export interface PreferencesData {
  auto_grammar_check: boolean;
  auto_expression_assist: boolean;
  daily_review_goal: number | null;
  ui_language: "zh" | "en";
  ghost_hints_enabled: boolean;
}

export interface PreferencesResponse {
  data: PreferencesData;
  meta?: RequestMeta;
}

// Learning plans & tasks (Slice 9, ERD §13)

export interface LearningPlanData {
  id: string;
  title: string;
  goal: string | null;
  daily_target_minutes: number | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
}

export interface LearningPlanListResponse {
  data: { items: LearningPlanData[] };
  meta?: RequestMeta;
}

export interface LearningPlanResponse {
  data: LearningPlanData;
  meta?: RequestMeta;
}

export type LearningTaskStatus = "pending" | "in_progress" | "completed" | "cancelled";

export interface LearningTaskData {
  id: string;
  plan_id: string | null;
  task_type: "review" | "practice" | "writing";
  title: string;
  description: string | null;
  related_expression_id: string | null;
  related_question_id: string | null;
  scheduled_at: string | null;
  completed_at: string | null;
  status: LearningTaskStatus;
  created_at: string;
}

export interface LearningTaskListResponse {
  data: { items: LearningTaskData[] };
  meta?: RequestMeta;
}

export interface LearningTaskResponse {
  data: LearningTaskData;
  meta?: RequestMeta;
}

// AI usage analytics (Slice 9, API Spec §16)

export interface AiUsageTotals {
  total_calls: number;
  success_calls: number;
  error_calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
}

export interface AiUsageTotalsResponse {
  data: AiUsageTotals;
  meta?: RequestMeta;
}

export interface AiFeatureUsage {
  feature: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
}

export interface AiFeatureUsageListResponse {
  data: { items: AiFeatureUsage[] };
  meta?: RequestMeta;
}

export interface AiUsageTrendPoint {
  date: string;
  calls: number;
  estimated_cost: number;
}

export interface AiUsageTrendsResponse {
  data: { items: AiUsageTrendPoint[] };
  meta?: RequestMeta;
}

// Billing (Slice 10, contract 1.3.0, sandbox payments only)

export interface SubscriptionPlanData {
  id: string;
  code: string;
  name: string;
  price_monthly: number;
  currency: string;
  features: Record<string, boolean>;
  quota_ai_calls_monthly: number | null;
  quota_evaluations_monthly: number | null;
}

export interface BillingPlanListResponse {
  data: { items: SubscriptionPlanData[] };
  meta?: RequestMeta;
}

export interface SubscriptionData {
  plan_code: string;
  plan_name: string;
  status: string;
  started_at: string;
  current_period_start: string;
  current_period_end: string;
  cancelled_at: string | null;
}

export interface SubscriptionResponse {
  data: SubscriptionData;
  meta?: RequestMeta;
}

export interface CheckoutData {
  transaction_id: string;
  plan_code: string;
  amount: number;
  currency: string;
  provider: string;
  status: string;
}

export interface CheckoutResponse {
  data: CheckoutData;
  meta?: RequestMeta;
}

export interface BillingTransactionData {
  id: string;
  plan_id: string;
  provider: string;
  provider_ref: string;
  amount: number;
  currency: string;
  status: string;
  kind: string;
  created_at: string;
  completed_at: string | null;
}

export interface BillingHistoryResponse {
  data: { items: BillingTransactionData[] };
  meta?: RequestMeta;
}

export interface BillingUsageData {
  plan_code: string;
  period_start: string;
  ai_calls: number;
  evaluations: number;
  quota_ai_calls_monthly: number | null;
  quota_evaluations_monthly: number | null;
}

export interface BillingUsageResponse {
  data: BillingUsageData;
  meta?: RequestMeta;
}
