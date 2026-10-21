# -*- coding: utf-8 -*-
"""逻辑数据契约的 Pydantic 模型（SRS 3.2）。

约束要点：
- Memory 必填 memory_id / conversation_id / 非空 content / 非空 sources /
  record_status(ready|needs_review)；entity/attribute/value 可空不可猜测填充；
- session_time 为标准时间或 null，time_expression 保留原文或 null，
  event_time 为规范化事件时间或 null（BR-10 未知不补齐）；
- 证据以 (conversation_id, session_id, turn_id) 联合定位（SRS 3.1）；
- 查询级有效性五态 + 理由；原始 Memory 不因一次查询被改写（SRS 3.2）。
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

RecordStatus = Literal["ready", "needs_review"]
RelationType = Literal["RETAIN", "UPDATE", "SUPERSEDE", "CONFLICT"]
ValidityStatus = Literal["effective", "historical", "conflict", "uncertain", "irrelevant"]
AnswerStatus = Literal["answered", "insufficient_evidence", "unresolved_conflict"]


class SourceRef(BaseModel):
    """证据来源：会话内轮次（turn_id 为原始 dia_id，如 D19:1）。"""

    session_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)


class Memory(BaseModel):
    memory_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    entity: Optional[str] = None
    attribute: Optional[str] = None
    value: Optional[str] = None
    # 会话标准时间（该来源会话的解析时间；未知为 null）
    session_time: Optional[str] = None
    # 原始时间表达（如 "last Friday"），保留原文
    time_expression: Optional[str] = None
    # 规范化事件时间；无法解析时为 null，不以记录时间伪装（BR-10）
    event_time: Optional[str] = None
    sources: list[SourceRef] = Field(min_length=1)
    record_status: RecordStatus = "ready"

    @field_validator("content")
    @classmethod
    def _content_non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content 不能为空白")
        return v


class MemoryWithScore(BaseModel):
    """检索候选（FR-08：返回 ID、排序分数和来源）。"""

    memory: Memory
    score: float = Field(ge=0.0, le=1.0)


class Relation(BaseModel):
    relation_id: str
    query_id: str
    from_memory_id: str       # 方向统一为旧 → 新（BR-03 / BR-04）
    to_memory_id: str
    type: RelationType
    reason: str = Field(min_length=1)
    evidence_memory_ids: list[str] = []


class CandidateValidity(BaseModel):
    """查询级有效性 + 理由（不回写原始 Memory）。"""

    memory_id: str
    status: ValidityStatus
    reason: str = Field(min_length=1)


class AnswerResult(BaseModel):
    status: AnswerStatus
    text: Optional[str] = None
    cited_memory_ids: list[str] = []
    # status=unresolved_conflict 时说明分歧双方（FR-11）
    conflict_explanation: Optional[str] = None


class QueryResult(BaseModel):
    """问答完整结果（SRS 3.2 QueryResult 契约）。"""

    query_id: str
    conversation_id: str
    question: str
    # 显式时间条件（用户输入；null 表示默认当前）
    as_of: Optional[str] = None
    # 实际截止时间（BR-08 默认 = 对话可用历史末端；BR-09 显式截止）
    effective_cutoff: Optional[str] = None
    top_k: int
    candidates: list[MemoryWithScore]
    relations: list[Relation]
    validity: list[CandidateValidity]
    effective_memory_ids: list[str]
    conflict_memory_ids: list[str]
    answer: AnswerResult
    run_config: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# API 请求 / 响应模型
# ---------------------------------------------------------------------------


class ImportRequest(BaseModel):
    file_path: str = Field(min_length=1)
    dataset_version: Optional[str] = None
    dev_conversations: Optional[list[str]] = None
    test_conversations: Optional[list[str]] = None


class ImportConversationError(BaseModel):
    conversation_id: str
    location: str
    message: str


class ImportReport(BaseModel):
    dataset_version: str
    file_sha256: str
    imported: list[str] = []
    skipped: list[str] = []          # 已存在同版本而跳过（不重复写入）
    rejected: list[str] = []         # 校验失败被拒绝
    errors: list[ImportConversationError] = []
    session_count: int = 0
    turn_count: int = 0
    qa_count: int = 0


class BuildRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    force: bool = False   # 重新抽取全部会话（忽略既有会话级完成标记）


class BuildTaskStatus(BaseModel):
    task_id: str
    conversation_id: str
    status: str                      # pending / running / completed / partial_failed / failed
    progress_done: int
    progress_total: int
    success_count: int               # 成功写入记忆数
    failed_count: int                # 失败会话数 + 失败记忆数
    error_summary: Optional[str] = None
    created_at: str
    updated_at: str


class ConversationInfo(BaseModel):
    conversation_id: str
    split: str
    dataset_version: str
    imported_at: str
    session_count: int               # 有轮次的会话数
    turn_count: int
    memory_count: int


class MemoryListResponse(BaseModel):
    items: list[Memory]
    total: int
    page: int
    page_size: int
    has_more: bool


class EvidenceTurn(BaseModel):
    """证据回溯（FR-06）：原始轮次及会话信息。"""

    conversation_id: str
    session_id: str
    turn_id: str
    speaker: str
    text: str
    session_raw_time: Optional[str] = None
    session_parsed_time: Optional[str] = None


class MemoryEvidenceResponse(BaseModel):
    memory: Memory
    sources: list[EvidenceTurn]


class QueryRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    question: str
    as_of: Optional[str] = None      # ISO 日期或日期时间
    top_k: Optional[int] = Field(default=None, gt=0, le=100)

    @field_validator("question")
    @classmethod
    def _question_non_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("问题不能为空")
        return v


class ExportRequest(BaseModel):
    conversation_id: Optional[str] = None   # null 表示导出全部已构建记忆
