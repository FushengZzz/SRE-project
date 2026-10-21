/**
 * 与后端 Pydantic 契约（SRS 3.2 / backend/app/models.py）对应的前端类型。
 * 字段命名保持后端原样，避免在展示层做隐式转换。
 */

export type RecordStatus = 'ready' | 'needs_review';
export type RelationType = 'RETAIN' | 'UPDATE' | 'SUPERSEDE' | 'CONFLICT';
export type ValidityStatus =
  | 'effective'
  | 'historical'
  | 'conflict'
  | 'uncertain'
  | 'irrelevant';
export type AnswerStatus =
  | 'answered'
  | 'insufficient_evidence'
  | 'unresolved_conflict';

export interface SourceRef {
  session_id: string;
  turn_id: string;
}

export interface Memory {
  memory_id: string;
  conversation_id: string;
  content: string;
  entity: string | null;
  attribute: string | null;
  value: string | null;
  session_time: string | null;
  time_expression: string | null;
  event_time: string | null;
  sources: SourceRef[];
  record_status: RecordStatus;
}

export interface MemoryWithScore {
  memory: Memory;
  score: number;
}

export interface Relation {
  relation_id: string;
  query_id: string;
  from_memory_id: string;
  to_memory_id: string;
  type: RelationType;
  reason: string;
  evidence_memory_ids: string[];
}

export interface CandidateValidity {
  memory_id: string;
  status: ValidityStatus;
  reason: string;
}

export interface AnswerResult {
  status: AnswerStatus;
  text: string | null;
  cited_memory_ids: string[];
  conflict_explanation: string | null;
}

export interface QueryResult {
  query_id: string;
  conversation_id: string;
  question: string;
  as_of: string | null;
  effective_cutoff: string | null;
  top_k: number;
  candidates: MemoryWithScore[];
  relations: Relation[];
  validity: CandidateValidity[];
  effective_memory_ids: string[];
  conflict_memory_ids: string[];
  answer: AnswerResult;
  run_config: Record<string, unknown>;
}

export interface ConversationInfo {
  conversation_id: string;
  split: string;
  dataset_version: string;
  imported_at: string;
  session_count: number;
  turn_count: number;
  memory_count: number;
}

export interface MemoryListResponse {
  items: Memory[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface EvidenceTurn {
  conversation_id: string;
  session_id: string;
  turn_id: string;
  speaker: string;
  text: string;
  session_raw_time: string | null;
  session_parsed_time: string | null;
}

export interface MemoryEvidenceResponse {
  memory: Memory;
  sources: EvidenceTurn[];
}

export interface Health {
  status: string;
  llm_provider: string;
  llm_model: string | null;
}

export interface QueryRequest {
  conversation_id: string;
  question: string;
  as_of?: string;
  top_k?: number;
}

export interface MemoryListParams {
  conversation_id: string;
  entity?: string;
  keyword?: string;
  record_status?: RecordStatus;
  page?: number;
  page_size?: number;
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
}
