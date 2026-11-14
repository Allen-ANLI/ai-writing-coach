// AUTO-GENERATED from contracts/openapi.yaml (info.version 1.1.1).
// Do not edit by hand: run `npm run generate:api` after contract changes.
// Open response bodies the contract does not define are mirrored in ./api.ts.

export interface HealthResponse {
  "data": {
    "status": "ok";
    "database": "connected";
  };
  "meta"?: {
    "request_id"?: string;
  };
}

export interface ErrorResponse {
  "error": {
    "code": string;
    "message": string;
    "details"?: {
      "field"?: string;
      "reason"?: string;
    }[];
  };
  "meta"?: {
    "request_id"?: string;
  };
}

export interface TextRange {
  "start": number;
  "end": number;
  "offset_unit": "unicode_codepoint";
}

export interface WorkingDocumentUpdate {
  "base_revision": number;
  "client_revision": number;
  "content_json": Record<string, unknown>;
  "plain_text"?: string;
  "word_count"?: number;
}

export interface WorkingDocumentSaved {
  "data": {
    "essay_id"?: string;
    "server_revision"?: number;
    "client_revision"?: number;
    "saved"?: boolean;
    "saved_at"?: string;
  };
}

export interface GrammarIssue {
  "id"?: string;
  "category"?: string;
  "sub_category"?: string | null;
  "source"?: "rule_engine" | "llm" | "hybrid";
  "source_server_revision"?: number;
  "essay_version_id"?: string | null;
  "start_offset"?: number;
  "end_offset"?: number;
  "offset_unit"?: "unicode_codepoint";
  "anchor_text"?: string;
  "short_explanation"?: string | null;
  "suggestions"?: {
    "id"?: string;
    "display_text"?: string;
    "answer_revealed"?: false;
  }[];
  "status"?: "detected" | "resolved" | "ignored" | "stale";
}

export interface GrammarCheckResponse {
  "data": {
    "server_revision"?: number;
    "client_revision"?: number;
    "check_status"?: "completed" | "partial";
    "issues"?: GrammarIssue[];
  };
}

export interface IssueValidationRequest {
  "issue_id": string;
  "base_revision": number;
  "client_revision": number;
  "content_json": Record<string, unknown>;
  "plain_text": string;
  "word_count"?: number;
  "modified_range": TextRange;
}

export interface TeachingRequest {
  "server_revision": number;
  "client_revision": number;
  "current_sentence": string;
  "paragraph_context"?: string | null;
  "user_current_text"?: string | null;
}

export interface EvaluationCreate {
  "version_id": string;
  "evaluation_type": "ielts" | "general";
  "task_type"?: "task1" | "task2" | null;
}

export interface RewriteAccept {
  "base_revision": number;
  "client_revision": number;
}

export interface SnapshotCreate {
  "source_revision": number;
  "version_type": "original" | "checkpoint" | "assisted" | "ai_rewrite" | "final";
  "label"?: string | null;
}

export type GenericObject = Record<string, unknown>;

export interface IssueValidationResponse {
  "data": {
    "issue_id"?: string;
    "validation_status"?: "correct" | "incorrect" | "needs_review";
    "is_resolved"?: boolean;
    "server_revision"?: number;
  };
}

export interface TeachingResponse {
  "data": {
    "teaching_id"?: string;
    "issue_id"?: string;
    "source_server_revision"?: number;
    "title"?: string;
    "why_wrong"?: string;
    "grammar_rule"?: string;
    "recommended_correction"?: string;
    "personalized_note"?: string | null;
  };
}
