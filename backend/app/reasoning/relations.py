# -*- coding: utf-8 -*-
"""B5 · 关系判定入口（FR-09）。

- relation_mode=rules（M4 默认）：确定性规则（app/reasoning/rules.py）；
- relation_mode=llm：使用 LLM 比较候选并输出四类关系 + 端点 + 理由 + 证据；
  LLM 失败或输出非法时自动回退规则结果（NFR-03，不无限阻塞）；
- 端点 ID 必须来自候选集合，类型必须为四类之一，逐条校验后丢弃非法项；
- 关系循环 / 引用缺失由校验兜底（BR-07 的输入侧约束）。
"""
from __future__ import annotations

from typing import Any

from ..config import Settings, get_settings
from ..errors import AppError
from ..llm.client import LLMClient
from ..llm.prompts import RELATION_SYSTEM, relation_user
from . import rules

_VALID_TYPES = {"RETAIN", "UPDATE", "SUPERSEDE", "CONFLICT"}


def _to_relation_items(relations: list[dict[str, Any]], query_id: str) -> list[dict[str, Any]]:
    """为规则输出包装 relation_id / query_id。"""
    out = []
    for i, rel in enumerate(relations, 1):
        out.append({
            "relation_id": f"rel_{query_id}_{i}",
            "query_id": query_id,
            **rel,
        })
    return out


def judge_relations(
    question: str,
    candidates: list[dict[str, Any]],
    query_id: str,
    *,
    settings: Settings | None = None,
    client: LLMClient | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """判定候选间关系。返回 (带 ID 的关系列表, 实际使用的模式)。"""
    s = settings or get_settings()
    fallback = lambda: (_to_relation_items(
        rules.judge_relations_rules(question, candidates), query_id), "rules")

    if s.relation_mode != "llm" or client is None or client.provider == "mock":
        return fallback()

    try:
        raw = client.chat_json(
            kind="judge_relations",
            system=RELATION_SYSTEM,
            user=relation_user(question, candidates),
            context={"question": question, "candidates": candidates},
        )
    except AppError:
        # LLM 不可用 / 超时：回退规则（记录于 run_config.used_relation_mode）
        return fallback()

    if not isinstance(raw, list):
        return fallback()

    candidate_ids = {c["memory_id"] for c in candidates}
    cleaned: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        f, t = item.get("from_memory_id"), item.get("to_memory_id")
        rtype = item.get("type")
        reason = item.get("reason")
        if (f not in candidate_ids or t not in candidate_ids or f == t
                or rtype not in _VALID_TYPES or not str(reason or "").strip()):
            continue  # 引用缺失 / 自环 / 非法类型：丢弃（BR-07）
        cleaned.append({
            "from_memory_id": f,
            "to_memory_id": t,
            "type": rtype,
            "reason": str(reason).strip(),
            "evidence_memory_ids": [
                x for x in (item.get("evidence_memory_ids") or [])
                if x in candidate_ids
            ],
        })
    if not cleaned:
        return fallback()
    return _to_relation_items(cleaned, query_id), "llm"
