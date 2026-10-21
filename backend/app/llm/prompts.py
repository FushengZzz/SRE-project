# -*- coding: utf-8 -*-
"""提示词模板（版本随配置记录到导出与查询结果，NFR-04 可复现性）。

调用方传入结构化数据，gold 标注（qa.answer / evidence / observation /
event_summary）不会出现在任何提示词中（SRS 3.1 数据隔离）。
"""
from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# 记忆抽取
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM = """You are a memory extraction engine for long-term conversations.
Given one session of a two-speaker conversation, extract structured memories of
stable facts worth remembering: personal states, plans, events, preferences,
relationships, occupations, achievements.

Rules:
1. Each memory must be grounded ONLY in the given turns. Never invent facts.
2. `source_turn_ids` must be dia_ids that appear in the given turns.
3. entity / attribute / value: fill only when clearly extractable; use null
   when uncertain. NEVER guess-fill.
4. content: one concise standalone sentence in the conversation's language.
5. time_expression: copy the original temporal phrase (e.g. "last Friday"),
   or null.
6. event_time: normalized date (YYYY-MM-DD) ONLY if the event date is
   explicitly stated or trivially derivable from the session date plus the
   expression; otherwise null. Do NOT fabricate dates or timezones.
7. record_status: "ready" for clear extractions, "needs_review" for
   uncertain ones.
8. Output ONLY a JSON array. Each element:
{"content": str, "entity": str|null, "attribute": str|null, "value": str|null,
 "time_expression": str|null, "event_time": str|null,
 "source_turn_ids": [str], "record_status": "ready"|"needs_review"}
Output [] if nothing worth extracting."""


def extract_user(session: dict[str, Any]) -> str:
    turns_text = "\n".join(f"[{t['turn_id']}] {t['speaker']}: {t['text']}" for t in session["turns"])
    return (
        f"Conversation: {session['conversation_id']}, session {session['session_id']}, "
        f"session date/time: {session['raw_time']}\n\nTurns:\n{turns_text}\n\n"
        "Extract memories as a JSON array."
    )


# ---------------------------------------------------------------------------
# 关系判定
# ---------------------------------------------------------------------------

RELATION_SYSTEM = """You compare retrieved memory candidates against each other
for a given question. Judge whether, for the same entity and the same
attribute/event, a newer fact updates (UPDATE: stage progression of one process),
supersedes (SUPERSEDE: replaces the old state for the same query scope),
conflicts with (CONFLICT: incompatible under the same time condition, no
resolution basis), or is compatible with (RETAIN) an older fact.

Rules:
1. Only compare memories about the SAME entity and the SAME attribute/event.
   Different entities or unrelated attributes must NOT be related (BR-01).
2. Direction is always old -> new (from_memory_id = older, to_memory_id = newer)
   for UPDATE / SUPERSEDE (BR-03, BR-04).
3. Facts at different times are NOT automatically a conflict; mere later
   source time is NOT a basis for replacement (BR-05, BR-06).
4. If you cannot decide, emit no relation for the pair.
5. Output ONLY a JSON array. Each element:
{"from_memory_id": str, "to_memory_id": str,
 "type": "RETAIN"|"UPDATE"|"SUPERSEDE"|"CONFLICT", "reason": str,
 "evidence_memory_ids": [str]}
Output [] if no pair is comparable."""


def relation_user(question: str, candidates: list[dict[str, Any]]) -> str:
    cand_text = json.dumps(candidates, ensure_ascii=False, indent=1)
    return f"Question: {question}\n\nCandidates (ordered by retrieval score):\n{cand_text}\n\nCompare comparable pairs and output a JSON array."


# ---------------------------------------------------------------------------
# 回答生成
# ---------------------------------------------------------------------------

ANSWER_SYSTEM = """You answer the user's question ONLY from the provided
effective memories of the conversation. Cite the memory_ids that support
your answer.

Rules:
1. Use ONLY the provided memories. Never use outside knowledge (BR-12).
2. Answer in the same language as the question.
3. If the memories do not contain the answer, reply exactly {"answer": "",
   "cited_memory_ids": []}.
4. Output ONLY a JSON object: {"answer": str, "cited_memory_ids": [str]}"""


def answer_user(question: str, memories: list[dict[str, Any]]) -> str:
    mem_text = json.dumps(memories, ensure_ascii=False, indent=1)
    return f"Question: {question}\n\nEffective memories (best first):\n{mem_text}\n\nAnswer as JSON."
