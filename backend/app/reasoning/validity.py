# -*- coding: utf-8 -*-
"""B5 · 查询级有效性解析（FR-10）。

职责：组合候选 + 关系 + 时间条件，输出逐条有效性（五态 + 理由）、
有效集合与冲突集合；不回写原始 Memory（SRS 3.2）。
"""
from __future__ import annotations

from typing import Any

from ..config import Settings, get_settings
from . import rules


def resolve_validity(
    candidates: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """解析有效性。

    返回 (逐条有效性列表, effective_ids, conflict_ids)。
    """
    s = settings or get_settings()
    items = rules.resolve_validity_rules(
        candidates, relations,
        irrelevant_score_threshold=s.irrelevant_score_threshold,
    )
    effective = [x["memory_id"] for x in items if x["status"] == "effective"]
    conflict = [x["memory_id"] for x in items if x["status"] == "conflict"]
    return items, effective, conflict
