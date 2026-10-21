# -*- coding: utf-8 -*-
"""B2 · 记忆抽取（FR-02）。

- 从一个会话的原始轮次抽取候选记忆；
- 只允许引用该会话内真实存在的 dia_id（防幻觉定位）；
- entity/attribute/value 无法抽取时保留 content，不猜测填充（SRS 3.2）；
- event_time 无法解析时为 null，不以记录时间伪装（BR-10）；
- memory_id 由 (conversation_id, content, 来源轮次) 哈希确定，
  保证构建重试幂等（FR-03 不重复写入）。
"""
from __future__ import annotations

import hashlib
from typing import Any

from ..llm.client import ChatKind, LLMClient
from ..llm.prompts import EXTRACT_SYSTEM, extract_user


class ExtractionItemError(Exception):
    """单条候选记忆校验失败（记录位置与原因，不中断整个会话）。"""

    def __init__(self, index: int, message: str):
        super().__init__(message)
        self.index = index
        self.message = message


def make_memory_id(conversation_id: str, content: str, turn_ids: list[str]) -> str:
    """确定性 memory_id：同内容 + 同来源 → 同 ID（重试幂等）。"""
    basis = "|".join([conversation_id, content.strip(), ",".join(sorted(set(turn_ids)))])
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:10]
    return f"{conversation_id}_m_{digest}"


def extract_session_memories(
    client: LLMClient,
    *,
    conversation_id: str,
    session: dict[str, Any],
    task_id: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """抽取单个会话的记忆。

    返回 (合格记忆列表, 单条失败原因列表)。会话级失败（模型不可用 /
    超时）直接抛出，由构建任务层记录。
    """
    valid_turn_ids = {t["turn_id"] for t in session["turns"]}
    prompt_session = {
        "conversation_id": conversation_id,
        "session_id": session["session_id"],
        "raw_time": session["raw_time"],
        "turns": [
            {"turn_id": t["turn_id"], "speaker": t["speaker"], "text": t["text"]}
            for t in session["turns"]
        ],
    }
    raw_items: Any = client.chat_json(
        kind="extract_memories",  # type: ignore[arg-type]
        system=EXTRACT_SYSTEM,
        user=extract_user(prompt_session),
        context={"session": prompt_session},
    )
    if not isinstance(raw_items, list):
        raise ValueError("抽取结果不是 JSON 数组")

    memories: list[dict[str, Any]] = []
    item_errors: list[str] = []
    for i, item in enumerate(raw_items):
        try:
            memories.append(_validate_item(item, i, conversation_id, session,
                                           valid_turn_ids, task_id))
        except ExtractionItemError as e:
            item_errors.append(f"第 {e.index} 条候选记忆被丢弃：{e.message}")
    return memories, item_errors


def _validate_item(
    item: Any,
    index: int,
    conversation_id: str,
    session: dict[str, Any],
    valid_turn_ids: set[str],
    task_id: str,
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ExtractionItemError(index, "不是对象")

    content = item.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ExtractionItemError(index, "content 缺失或为空")

    source_ids = item.get("source_turn_ids")
    if not isinstance(source_ids, list) or not source_ids:
        raise ExtractionItemError(index, "source_turn_ids 缺失或为空")
    turn_ids: list[str] = []
    for sid in source_ids:
        if not isinstance(sid, str) or sid not in valid_turn_ids:
            raise ExtractionItemError(
                index, f"来源轮次 {sid!r} 不在会话 {session['session_id']} 内（拒绝幻觉引用）")
        if sid not in turn_ids:
            turn_ids.append(sid)

    entity = _opt_str(item.get("entity"))
    attribute = _opt_str(item.get("attribute"))
    value = _opt_str(item.get("value"))
    time_expression = _opt_str(item.get("time_expression"))
    event_time = _opt_date(item.get("event_time"))
    record_status = item.get("record_status", "ready")
    if record_status not in ("ready", "needs_review"):
        record_status = "needs_review"

    sources = [
        {"session_id": session["session_id"], "turn_id": tid} for tid in turn_ids
    ]
    return {
        "memory_id": make_memory_id(conversation_id, content, turn_ids),
        "conversation_id": conversation_id,
        "content": content.strip(),
        "entity": entity,
        "attribute": attribute,
        "value": value,
        "session_time": session.get("parsed_time"),
        "time_expression": time_expression,
        "event_time": event_time,
        "sources": sources,
        "record_status": record_status,
        "build_task_id": task_id,
    }


def _opt_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _opt_date(v: Any) -> str | None:
    """规范化事件时间：仅接受 YYYY-MM-DD[THH:MM[:SS]]，其余置空不补齐（BR-10）。"""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    # 仅校验基本形态，容忍 YYYY-MM-DD 与 ISO 时间两种
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        head = s[:10]
        try:
            parts = [int(x) for x in head.split("-")]
            if 1 <= parts[1] <= 12 and 1 <= parts[2] <= 31:
                return s
        except ValueError:
            pass
    return None
