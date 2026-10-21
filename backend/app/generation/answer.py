# -*- coding: utf-8 -*-
"""B6 · 回答生成（FR-11）。

- 仅基于有效记忆作答，引用支撑 memory_id（NFR-02 可回溯）；
- 证据不足 → insufficient_evidence；
- 存在影响结论且无法消解的冲突 → unresolved_conflict 并说明分歧，
  不把未决冲突表述为确定事实；
- 不使用模型外部知识补成对话事实（BR-12）。
"""
from __future__ import annotations

from typing import Any

from ..config import Settings, get_settings
from ..llm.client import LLMClient
from ..llm.prompts import ANSWER_SYSTEM, answer_user
from ..models import AnswerResult

# 冲突候选分数达到最高分的该比例时，视为“影响结论”
MATERIAL_CONFLICT_RATIO = 0.3


def generate_answer(
    client: LLMClient,
    question: str,
    *,
    candidates: list[dict[str, Any]],
    effective: list[dict[str, Any]],
    conflict_memories: list[dict[str, Any]],
    conflict_relations: list[dict[str, Any]],
    settings: Settings | None = None,
) -> AnswerResult:
    s = settings or get_settings()

    # 1. 材料性冲突：分数较高的冲突候选影响结论 → unresolved_conflict
    if conflict_memories:
        max_score = max((c.get("score", 0.0) for c in candidates), default=0.0)
        material = [
            c for c in conflict_memories
            if max_score <= 0 or c.get("score", 0.0) >= MATERIAL_CONFLICT_RATIO * max_score
        ]
        if material:
            sides = " | ".join(
                f"{c['content']}（{c['memory_id']}）" for c in material[:4]
            )
            rel_reasons = "；".join(
                r["reason"] for r in conflict_relations[:2]
            ) or "同一时间条件下事实不相容"
            return AnswerResult(
                status="unresolved_conflict",
                text=None,
                cited_memory_ids=[c["memory_id"] for c in material],
                conflict_explanation=(
                    f"存在无法消解的冲突，不能给出确定结论。分歧双方：{sides}。"
                    f"原因：{rel_reasons}（BR-05/06，保留双方证据待人工核查）"
                ),
            )

    # 2. 无有效记忆 → 证据不足
    if not effective:
        return AnswerResult(
            status="insufficient_evidence",
            text="在所选对话的可用记忆中，未找到足以回答该问题的证据。",
            cited_memory_ids=[],
            conflict_explanation=None,
        )

    # 3. 基于有效记忆生成（LLM 或 mock 抽取式）
    try:
        raw = client.chat_json(
            kind="generate_answer",
            system=ANSWER_SYSTEM,
            user=answer_user(question, effective),
            context={"question": question, "memories": effective},
        )
    except Exception:
        # 模型不可用 / 超时：不伪造答案，向上抛出（UC-03 异常分支）
        raise

    if not isinstance(raw, dict):
        raw = {}
    answer_text = str(raw.get("answer") or "").strip()
    effective_ids = {c["memory_id"] for c in effective}
    cited = [
        cid for cid in (raw.get("cited_memory_ids") or [])
        if isinstance(cid, str) and cid in effective_ids
    ]
    if not answer_text:
        return AnswerResult(
            status="insufficient_evidence",
            text="在所选对话的可用记忆中，未找到足以回答该问题的证据。",
            cited_memory_ids=[],
            conflict_explanation=None,
        )
    if not cited:
        # 引用缺失时退回分数最高的有效记忆，保证可回溯（NFR-02）
        cited = [effective[0]["memory_id"]]
    return AnswerResult(
        status="answered",
        text=answer_text,
        cited_memory_ids=cited,
        conflict_explanation=None,
    )
