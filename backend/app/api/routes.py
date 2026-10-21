# -*- coding: utf-8 -*-
"""B7 · REST API 路由（SRS 7.1 逻辑操作 → HTTP）。

| 逻辑操作 | HTTP |
|---|---|
| 导入 | POST /api/import |
| 导入并构建（任务） | POST /api/build、GET /api/build/{task_id} |
| 列出记忆 | GET /api/memories |
| 证据详情 | GET /api/memories/{id}/evidence、GET /api/turns/{conv}/{turn_id} |
| 导出 | POST /api/export |
| 问答 | POST /api/query、GET /api/query/{query_id} |
| 批量评测 | POST /api/eval/run（Phase 2 占位，FR-13） |
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from ..config import get_settings
from ..data.importer import import_dataset
from ..database import Database, get_database, row_to_memory
from ..errors import AppError, InvalidParamError, NotCapableError, NotFoundError
from ..export.exporter import export_to_file
from ..llm.client import get_llm_client
from ..memory.builder import create_build_task, get_build_status, run_build_task
from ..models import (
    BuildRequest,
    BuildTaskStatus,
    ConversationInfo,
    EvidenceTurn,
    ExportRequest,
    ImportReport,
    ImportRequest,
    Memory,
    MemoryEvidenceResponse,
    MemoryListResponse,
    MemoryWithScore,
    QueryRequest,
    QueryResult,
    SourceRef,
)
from ..query_service import get_query_result, run_query

router = APIRouter(prefix="/api", tags=["memory-api"])


# ---------------------------------------------------------------------------
# 基础
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "llm_provider": s.llm_provider,
        "llm_model": s.llm_model,
    }


@router.get("/conversations", response_model=list[ConversationInfo])
def list_conversations(db: Database = Depends(get_database)) -> list[ConversationInfo]:
    convs = db.query("SELECT * FROM conversations ORDER BY conversation_id")
    out: list[ConversationInfo] = []
    for c in convs:
        cid = c["conversation_id"]
        sess = db.query_one(
            "SELECT COUNT(*) AS n FROM sessions WHERE conversation_id=? AND has_turns=1", (cid,))
        turns = db.query_one(
            "SELECT COUNT(*) AS n FROM turns WHERE conversation_id=?", (cid,))
        mems = db.query_one(
            "SELECT COUNT(*) AS n FROM memories WHERE conversation_id=?", (cid,))
        out.append(ConversationInfo(
            conversation_id=cid,
            split=c["split"],
            dataset_version=c["dataset_version"],
            imported_at=c["imported_at"],
            session_count=sess["n"],
            turn_count=turns["n"],
            memory_count=mems["n"],
        ))
    return out


# ---------------------------------------------------------------------------
# 导入 / 构建（FR-01 / FR-02 / FR-03）
# ---------------------------------------------------------------------------

@router.post("/import", response_model=ImportReport)
def api_import(
    req: ImportRequest,
    db: Database = Depends(get_database),
) -> ImportReport:
    return import_dataset(
        db,
        req.file_path,
        dataset_version=req.dataset_version,
        dev_conversations=req.dev_conversations,
        test_conversations=req.test_conversations,
    )


@router.post("/build", response_model=BuildTaskStatus)
def api_build(
    req: BuildRequest,
    background: BackgroundTasks,
    db: Database = Depends(get_database),
) -> BuildTaskStatus:
    status = create_build_task(db, req.conversation_id, force=req.force)
    # 校验配置可用（无 Key 用 openai 等错误提前暴露，而不是任务里失败）
    get_llm_client(get_settings())
    db.close()
    background.add_task(_run_build_bg, status.task_id)
    return status


def _run_build_bg(task_id: str) -> None:
    db = get_database()
    try:
        run_build_task(db, task_id)
    finally:
        db.close()


@router.get("/build/{task_id}", response_model=BuildTaskStatus)
def api_build_status(task_id: str, db: Database = Depends(get_database)) -> BuildTaskStatus:
    return get_build_status(db, task_id)


# ---------------------------------------------------------------------------
# 记忆浏览与证据回溯（FR-05 / FR-06）
# ---------------------------------------------------------------------------

@router.get("/memories", response_model=MemoryListResponse)
def list_memories(
    conversation_id: str = Query(min_length=1),
    entity: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    record_status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Database = Depends(get_database),
) -> MemoryListResponse:
    where = ["conversation_id = ?"]
    params: list = [conversation_id]

    conv = db.query_one(
        "SELECT conversation_id FROM conversations WHERE conversation_id=?",
        (conversation_id,))
    if conv is None:
        raise NotFoundError(f"对话不存在：{conversation_id}")

    if entity:
        where.append("LOWER(entity) = LOWER(?)")
        params.append(entity.strip())
    if keyword:
        where.append("content LIKE ?")
        params.append(f"%{keyword.strip()}%")
    if record_status:
        if record_status not in ("ready", "needs_review"):
            raise InvalidParamError("record_status 仅允许 ready / needs_review")
        where.append("record_status = ?")
        params.append(record_status)

    where_sql = " AND ".join(where)
    total_row = db.query_one(
        f"SELECT COUNT(*) AS n FROM memories WHERE {where_sql}", tuple(params))
    total = total_row["n"]
    offset = (page - 1) * page_size
    rows = db.query(
        f"SELECT * FROM memories WHERE {where_sql} "
        f"ORDER BY session_time, memory_id LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    )
    items = [Memory.model_validate(row_to_memory(r)) for r in rows]
    return MemoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(items)) < total,
    )


@router.get("/memories/{memory_id}", response_model=Memory)
def get_memory(memory_id: str, db: Database = Depends(get_database)) -> Memory:
    row = db.query_one("SELECT * FROM memories WHERE memory_id=?", (memory_id,))
    if row is None:
        raise NotFoundError(f"记忆不存在：{memory_id}")
    return Memory.model_validate(row_to_memory(row))


@router.get("/memories/{memory_id}/evidence", response_model=MemoryEvidenceResponse)
def get_memory_evidence(
    memory_id: str,
    db: Database = Depends(get_database),
) -> MemoryEvidenceResponse:
    """证据回溯：展示该记忆全部来源轮次及会话信息（FR-06 多来源全部可查看）。"""
    row = db.query_one("SELECT * FROM memories WHERE memory_id=?", (memory_id,))
    if row is None:
        raise NotFoundError(f"记忆不存在：{memory_id}")
    memory = Memory.model_validate(row_to_memory(row))

    sources: list[EvidenceTurn] = []
    for src in memory.sources:
        turn = db.query_one(
            "SELECT t.*, s.raw_time AS session_raw_time, s.parsed_time AS session_parsed_time "
            "FROM turns t JOIN sessions s "
            "ON t.conversation_id = s.conversation_id AND t.session_id = s.session_id "
            "WHERE t.conversation_id=? AND t.session_id=? AND t.turn_id=?",
            (memory.conversation_id, src.session_id, src.turn_id),
        )
        if turn is None:
            # 无法定位时报告错误，不展示其他轮次替代（FR-06）
            raise NotFoundError(
                f"记忆 {memory_id} 的来源轮次无法定位："
                f"(session {src.session_id}, turn {src.turn_id})")
        sources.append(EvidenceTurn(
            conversation_id=turn["conversation_id"],
            session_id=turn["session_id"],
            turn_id=turn["turn_id"],
            speaker=turn["speaker"],
            text=turn["text"],
            session_raw_time=turn["session_raw_time"],
            session_parsed_time=turn["session_parsed_time"],
        ))
    return MemoryEvidenceResponse(memory=memory, sources=sources)


@router.get("/turns/{conversation_id}/{turn_id}", response_model=EvidenceTurn)
def get_turn(
    conversation_id: str,
    turn_id: str,
    db: Database = Depends(get_database),
) -> EvidenceTurn:
    turn = db.query_one(
        "SELECT t.*, s.raw_time AS session_raw_time, s.parsed_time AS session_parsed_time "
        "FROM turns t JOIN sessions s "
        "ON t.conversation_id = s.conversation_id AND t.session_id = s.session_id "
        "WHERE t.conversation_id=? AND t.turn_id=?",
        (conversation_id, turn_id),
    )
    if turn is None:
        raise NotFoundError(
            f"轮次不存在：({conversation_id}, {turn_id})")
    return EvidenceTurn(
        conversation_id=turn["conversation_id"],
        session_id=turn["session_id"],
        turn_id=turn["turn_id"],
        speaker=turn["speaker"],
        text=turn["text"],
        session_raw_time=turn["session_raw_time"],
        session_parsed_time=turn["session_parsed_time"],
    )


# ---------------------------------------------------------------------------
# 导出（FR-04）
# ---------------------------------------------------------------------------

@router.post("/export")
def api_export(req: ExportRequest, db: Database = Depends(get_database)) -> Response:
    """导出 JSON：落盘 exports/ 并作为附件返回（可重新解析，UTF-8）。"""
    path, payload = export_to_file(db, req.conversation_id)
    filename = Path(path).name
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Path": str(path),
            "X-Export-Memory-Count": str(payload.get("memory_count", 0)),
        },
    )


# ---------------------------------------------------------------------------
# 问答（FR-07 ~ FR-12，UC-03）
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResult)
def api_query(
    req: QueryRequest,
    db: Database = Depends(get_database),
) -> QueryResult:
    return run_query(db, req)


@router.get("/query/{query_id}", response_model=QueryResult)
def api_query_get(query_id: str, db: Database = Depends(get_database)) -> QueryResult:
    return get_query_result(db, query_id)


# ---------------------------------------------------------------------------
# 批量评测（FR-13，Phase 2 占位）
# ---------------------------------------------------------------------------

@router.post("/eval/run")
def api_eval_run() -> None:
    raise NotCapableError(
        "批量评测在 Phase 2（M5 冻结评测）提供；当前里程碑聚焦必做链路"
        "（SRS 2.3：评测工具应可运行，但不预写最终结果）"
    )
