# -*- coding: utf-8 -*-
"""B5 · 关系判定与有效性解析的纯规则实现（无 LLM 依赖，可独立单测）。

业务规则映射：
- BR-01：先判断实体/属性/时间/语义可比较性，不强行建立关系；
- BR-02：单条候选不制造虚假双节点关系；RETAIN 表示兼容保留；
- BR-03/04：UPDATE / SUPERSEDE 方向统一为旧 → 新；
- BR-05：不同时间不构成冲突；CONFLICT 语义对称、输出不重复；
- BR-06：无消解依据时保留双方并标记，不默认新为真；
- BR-07：无法判定即不伪造关系，由有效性阶段标 uncertain。

candidates 为扁平化字典列表：
{memory_id, score, content, entity, attribute, value,
 session_time, event_time, time_expression}
"""
from __future__ import annotations

from typing import Any

# 视为「阶段推进过程」的属性关键词（→ UPDATE）；其余同属性不同值视为 SUPERSEDE
PROCESS_ATTRIBUTE_KEYWORDS = (
    "plan", "progress", "status", "stage", "process",
    "application", "career", "education", "adoption", "search", "study",
)
# 无法结构化比较的通用属性（mock 抽取的兜底属性），不参与关系判定
NON_COMPARABLE_ATTRIBUTES = {"statement", "note", "misc"}


def _time_key(c: dict[str, Any]) -> str | None:
    """事件时间优先（BR-10），缺失时退回会话时间（记录时间）。"""
    return c.get("event_time") or c.get("session_time") or None


def _norm_value(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    return s or None


def judge_relations_rules(
    question: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """规则版关系判定。返回关系条目（不含 relation_id / query_id，
    由调用方包装），方向旧 → 新。

    仅当 (entity, attribute) 可比较且实体与问题相关时判定；
    无法判定时不输出任何关系（BR-01 / BR-07）。
    """
    comparable = [
        c for c in candidates
        if c.get("entity") and c.get("attribute")
        and str(c["attribute"]).strip().lower() not in NON_COMPARABLE_ATTRIBUTES
    ]
    if len(comparable) < 2:
        return []

    # 分组：(entity.lower(), attribute.lower())
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in comparable:
        key = (str(c["entity"]).strip().lower(), str(c["attribute"]).strip().lower())
        groups.setdefault(key, []).append(c)

    q_lower = question.lower()
    entities_in_question = {
        key for key in groups if key[0] in q_lower
    }
    if not entities_in_question:
        # 兜底：所有候选仅围绕同一实体（如代词指代），仍允许判定该实体
        distinct_entities = {key[0] for key in groups}
        if len(distinct_entities) == 1:
            entities_in_question = set(groups.keys())
        else:
            return []

    relations: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for key in sorted(entities_in_question):
        group = groups[key]
        if len(group) < 2:
            continue  # BR-02：单条候选不制造双节点关系
        entity, attribute = key
        relations.extend(_judge_group(group, entity, attribute, seen_pairs))
    return relations


def _judge_group(
    group: list[dict[str, Any]],
    entity: str,
    attribute: str,
    seen_pairs: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    # 按时间排序（未知时间放最后，id 稳定排序）
    def sort_key(c: dict[str, Any]) -> tuple[int, str]:
        t = _time_key(c)
        return (0, t) if t else (1, c["memory_id"])

    ordered = sorted(group, key=sort_key)
    values = [(_norm_value(c.get("value")), c) for c in ordered]
    concrete = [v for v in values if v[0] is not None]

    # 全部值一致 → RETAIN（一条，旧 → 新）
    if concrete and len({v for v, _ in concrete}) == 1 and len(concrete) == len(ordered):
        first, last = ordered[0], ordered[-1]
        if first["memory_id"] != last["memory_id"]:
            out.append({
                "from_memory_id": first["memory_id"],
                "to_memory_id": last["memory_id"],
                "type": "RETAIN",
                "reason": (
                    f"{entity} 的 {attribute} 信息一致（{concrete[0][0]}），"
                    "多条证据互相兼容，全部保留（BR-02）"
                ),
                "evidence_memory_ids": [c["memory_id"] for c in ordered],
            })
        return out

    # 依次比较相邻（时间序）候选，形成更新链
    for (v_old, c_old), (v_new, c_new) in zip(values, values[1:]):
        pair = (min(c_old["memory_id"], c_new["memory_id"]),
                max(c_old["memory_id"], c_new["memory_id"]))
        if pair in seen_pairs:
            continue
        if v_old is None or v_new is None or v_old == v_new:
            continue  # 值缺失或一致：无可判定的差异，不伪造关系（BR-01）

        t_old, t_new = _time_key(c_old), _time_key(c_new)
        if t_old and t_new:
            if t_old == t_new:
                rel_type = "CONFLICT"
                reason = (
                    f"{entity} 的 {attribute} 在同一时间条件（{t_old}）下"
                    f"同时出现不相容陈述（{v_old!r} vs {v_new!r}），"
                    "现有证据不足以消解（BR-05）"
                )
            else:
                rel_type = (
                    "UPDATE"
                    if any(k in attribute for k in PROCESS_ATTRIBUTE_KEYWORDS)
                    else "SUPERSEDE"
                )
                if rel_type == "UPDATE":
                    reason = (
                        f"{entity} 的 {attribute} 存在阶段推进"
                        f"（{v_old!r} → {v_new!r}，{t_old} → {t_new}），"
                        "同一过程的新阶段更新当前状态，旧阶段保留用于历史问题（BR-03）"
                    )
                else:
                    reason = (
                        f"当前查询语义下，{entity} 的 {attribute} 新事实"
                        f"（{v_new!r}，{t_new}）替代旧状态（{v_old!r}，{t_old}），"
                        "方向旧 → 新（BR-04）"
                    )
        else:
            # 时间不可比且值不一致：无法消解 → 冲突，保留双方（BR-06）
            rel_type = "CONFLICT"
            reason = (
                f"{entity} 的 {attribute} 出现不相容陈述"
                f"（{v_old!r} vs {v_new!r}）且时间不可比，"
                "无消解依据，标记冲突并保留双方证据（BR-06）"
            )

        seen_pairs.add(pair)
        out.append({
            "from_memory_id": c_old["memory_id"],
            "to_memory_id": c_new["memory_id"],
            "type": rel_type,
            "reason": reason,
            "evidence_memory_ids": [c_old["memory_id"], c_new["memory_id"]],
        })
    return out


# ---------------------------------------------------------------------------
# 有效性解析（FR-10）
# ---------------------------------------------------------------------------

def resolve_validity_rules(
    candidates: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    *,
    irrelevant_score_threshold: float = 0.05,
) -> list[dict[str, Any]]:
    """查询级有效性五态解析。

    - CONFLICT 关系端点 → conflict（保留双方，BR-06）；
    - UPDATE / SUPERSEDE 的旧端 → historical、新端 → effective
      （历史问题仍可用旧记忆作证据，由 as_of 过滤保证，BR-11）；
    - RETAIN 端点 → effective（兼容保留）；
    - 未参与关系且检索分低于阈值 → irrelevant；
    - 其余 → effective。

    返回 [{memory_id, status, reason}]，不改写原始 Memory（SRS 3.2）。
    """
    conflict_ids: set[str] = set()
    old_side_ids: set[str] = set()
    new_side_ids: set[str] = set()
    retain_ids: set[str] = set()

    for rel in relations:
        f, t = rel["from_memory_id"], rel["to_memory_id"]
        rtype = rel["type"]
        if rtype == "CONFLICT":
            conflict_ids.update((f, t))
        elif rtype in ("UPDATE", "SUPERSEDE"):
            old_side_ids.add(f)
            new_side_ids.add(t)
        elif rtype == "RETAIN":
            retain_ids.update((f, t))

    results: list[dict[str, Any]] = []
    for c in candidates:
        mid = c["memory_id"]
        if mid in conflict_ids:
            results.append({
                "memory_id": mid,
                "status": "conflict",
                "reason": "与其他候选存在无法消解的冲突关系，保留双方证据待核查（BR-05/06）",
            })
        elif mid in old_side_ids:
            results.append({
                "memory_id": mid,
                "status": "historical",
                "reason": "被后续事实更新或替代；对更早时间点的问题仍是有效证据（BR-11）",
            })
        elif mid in new_side_ids:
            results.append({
                "memory_id": mid,
                "status": "effective",
                "reason": "更新链中的最新阶段，作为当前状态的有效证据（BR-03/04）",
            })
        elif mid in retain_ids:
            results.append({
                "memory_id": mid,
                "status": "effective",
                "reason": "与相关候选事实兼容，予以保留（BR-02）",
            })
        elif float(c.get("score", 0.0)) < irrelevant_score_threshold:
            results.append({
                "memory_id": mid,
                "status": "irrelevant",
                "reason": f"检索相似度过低（{c.get('score', 0.0):.4f} < 阈值 "
                          f"{irrelevant_score_threshold}），视为与问题无关",
            })
        else:
            results.append({
                "memory_id": mid,
                "status": "effective",
                "reason": "与问题相关且未发现更新或冲突关系，作为有效证据",
            })
    return results
