# -*- coding: utf-8 -*-
"""B3 · 统一 JSON 导出（FR-04）。

- 按对话或整个已构建集合导出 UTF-8 JSON；
- 包含 schema_version、记忆、数据清单与构建版本信息（SRS 3.3）；
- 导出前校验：ID 无重复、来源引用可定位（引用完整，NFR-02）；
- 导出后可被 JSON 重新解析（FR-04，tests 验证）。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from ..database import Database, row_to_memory
from ..errors import InvalidParamError, NotFoundError

SCHEMA_VERSION = "0.1"


def _load_memories(db: Database, conversation_id: str | None) -> list[dict[str, Any]]:
    if conversation_id:
        rows = db.query(
            "SELECT * FROM memories WHERE conversation_id=? "
            "ORDER BY session_time, memory_id",
            (conversation_id,),
        )
    else:
        rows = db.query(
            "SELECT * FROM memories ORDER BY conversation_id, session_time, memory_id"
        )
    return [row_to_memory(r) for r in rows]


def _validate_references(db: Database, memories: list[dict[str, Any]], conversation_id: str | None) -> None:
    """导出前校验：ID 唯一 + 每条来源轮次真实存在（无法定位即失败）。"""
    seen: set[str] = set()
    for m in memories:
        if m["memory_id"] in seen:
            raise InvalidParamError(f"导出中止：memory_id 重复 {m['memory_id']}")
        seen.add(m["memory_id"])
        for src in m["sources"]:
            row = db.query_one(
                "SELECT turn_id FROM turns WHERE conversation_id=? AND session_id=? AND turn_id=?",
                (m["conversation_id"], src["session_id"], src["turn_id"]),
            )
            if row is None:
                raise InvalidParamError(
                    f"导出中止：记忆 {m['memory_id']} 的来源 "
                    f"(session {src['session_id']}, turn {src['turn_id']}) 无法定位"
                )
    # 交叉对话混用检查（SRS 3.1：禁止跨对话）
    if conversation_id:
        for m in memories:
            if m["conversation_id"] != conversation_id:
                raise InvalidParamError(
                    f"导出中止：记忆 {m['memory_id']} 不属于对话 {conversation_id}")


def build_export_payload(
    db: Database,
    conversation_id: str | None,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """组装导出 payload（不落盘，便于 API 直接返回与测试重解析）。"""
    s = settings or get_settings()
    memories = _load_memories(db, conversation_id)

    if conversation_id:
        conv_row = db.query_one(
            "SELECT * FROM conversations WHERE conversation_id=?", (conversation_id,))
        if conv_row is None:
            raise NotFoundError(f"对话不存在：{conversation_id}")
        if not memories:
            raise NotFoundError(
                f"对话 {conversation_id} 尚未构建任何记忆，无法导出（请先执行构建）")
        _validate_references(db, memories, conversation_id)
        dataset_version = conv_row["dataset_version"]
        conv_ids = [conversation_id]
    else:
        if not memories:
            raise NotFoundError("当前没有任何已构建记忆，无法导出")
        _validate_references(db, memories, None)
        conv_rows = db.query("SELECT conversation_id, dataset_version FROM conversations")
        dataset_version = conv_rows[0]["dataset_version"] if conv_rows else s.dataset_version
        conv_ids = [r["conversation_id"] for r in conv_rows]

    # 数据清单（SRS 3.1）
    manifest_rows = db.query(
        "SELECT file_name, file_sha256, dataset_version, imported_at, conversation_ids "
        "FROM dataset_manifest ORDER BY id"
    )
    manifest = [
        {
            "file_name": r["file_name"],
            "file_sha256": r["file_sha256"],
            "dataset_version": r["dataset_version"],
            "imported_at": r["imported_at"],
            "conversation_ids": json.loads(r["conversation_ids"]),
        }
        for r in manifest_rows
    ]

    # 构建信息（NFR-04 可复现性）
    ready = sum(1 for m in memories if m["record_status"] == "ready")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "conversation_id": conversation_id,       # null = 全部已构建集合
        "conversation_ids": conv_ids,
        "memory_count": len(memories),
        "memories": memories,
        "data_manifest": manifest,
        "build_info": {
            "llm_provider": s.llm_provider,
            "llm_model": s.llm_model,
            "extract_prompt_version": s.extract_prompt_version,
            "ready_count": ready,
            "needs_review_count": len(memories) - ready,
        },
    }
    return payload


def export_to_file(
    db: Database,
    conversation_id: str | None,
    *,
    settings: Settings | None = None,
) -> tuple[Path, dict[str, Any]]:
    """导出到 exports/ 目录，返回 (文件路径, payload)。"""
    s = settings or get_settings()
    payload = build_export_payload(db, conversation_id, settings=s)
    out_dir = s.export_path
    out_dir.mkdir(parents=True, exist_ok=True)
    scope = conversation_id or "all"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"memories_{scope}_{stamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path, payload
