# -*- coding: utf-8 -*-
"""关系判定与有效性规则单元测试（BR-01 ~ BR-07 / BR-11，AT-09/10 相关）。"""
from __future__ import annotations

from app.reasoning import rules


def _cand(mid, entity, attribute, value, session_time, score=0.5, event_time=None):
    return {
        "memory_id": mid,
        "score": score,
        "content": f"content of {mid}",
        "entity": entity,
        "attribute": attribute,
        "value": value,
        "session_time": session_time,
        "event_time": event_time,
        "time_expression": None,
        "sources": [],
    }


class TestJudgeRelations:
    def test_single_candidate_no_relation(self):
        """BR-02：单条候选不制造虚假双节点关系。"""
        cands = [_cand("a", "Gina", "occupation", "unemployed", "2023-01-01")]
        assert rules.judge_relations_rules("Gina's job?", cands) == []

    def test_different_entity_no_relation(self):
        """BR-01：不同实体不强行建立关系。"""
        cands = [
            _cand("a", "Gina", "occupation", "unemployed", "2023-01-01"),
            _cand("b", "Jon", "occupation", "teacher", "2023-02-01"),
        ]
        assert rules.judge_relations_rules("Gina's job?", cands) == []

    def test_supersede_direction_old_to_new(self):
        """BR-04：新事实替代旧状态，方向旧 → 新。"""
        cands = [
            _cand("new", "Gina", "occupation", "online store", "2023-06-01", score=0.9),
            _cand("old", "Gina", "occupation", "unemployed", "2023-01-01", score=0.8),
        ]
        rels = rules.judge_relations_rules("What is Gina's job now?", cands)
        assert len(rels) == 1
        assert rels[0]["type"] == "SUPERSEDE"
        assert rels[0]["from_memory_id"] == "old"
        assert rels[0]["to_memory_id"] == "new"
        assert "旧" in rels[0]["reason"]

    def test_update_stage_progression(self):
        """BR-03：同一过程阶段推进标记 UPDATE，链式旧 → 新。"""
        cands = [
            _cand("s1", "Gina", "adoption_status", "researching", "2023-01-01"),
            _cand("s2", "Gina", "adoption_status", "applied", "2023-02-01"),
            _cand("s3", "Gina", "adoption_status", "passed", "2023-03-01"),
        ]
        rels = rules.judge_relations_rules("How is Gina's adoption?", cands)
        assert [r["type"] for r in rels] == ["UPDATE", "UPDATE"]
        assert rels[0]["from_memory_id"] == "s1" and rels[0]["to_memory_id"] == "s2"
        assert rels[1]["from_memory_id"] == "s2" and rels[1]["to_memory_id"] == "s3"

    def test_conflict_same_time_incompatible(self):
        """BR-05：同一时间条件不相容 → CONFLICT，输出不重复。"""
        cands = [
            _cand("x", "Gina", "age", "25", "2023-01-01"),
            _cand("y", "Gina", "age", "30", "2023-01-01"),
        ]
        rels = rules.judge_relations_rules("How old is Gina?", cands)
        assert len(rels) == 1
        assert rels[0]["type"] == "CONFLICT"
        assert "BR-05" in rels[0]["reason"]

    def test_incomparable_time_conflict_br06(self):
        """BR-06：时间不可比且值不一致 → 标记冲突保留双方。"""
        cands = [
            _cand("x", "Gina", "city", "London", None),
            _cand("y", "Gina", "city", "Paris", "2023-01-01"),
        ]
        rels = rules.judge_relations_rules("Where does Gina live?", cands)
        assert len(rels) == 1 and rels[0]["type"] == "CONFLICT"

    def test_retain_same_value(self):
        """BR-02：值一致 → RETAIN 兼容保留。"""
        cands = [
            _cand("a", "Gina", "pet", "dog", "2023-01-01"),
            _cand("b", "Gina", "pet", "dog", "2023-05-01"),
        ]
        rels = rules.judge_relations_rules("Does Gina have a pet?", cands)
        assert len(rels) == 1 and rels[0]["type"] == "RETAIN"
        assert rels[0]["from_memory_id"] == "a" and rels[0]["to_memory_id"] == "b"

    def test_fallback_single_entity_pronoun_question(self):
        """代词问题兜底：所有候选围绕同一实体时仍可判定。"""
        cands = [
            _cand("a", "Gina", "occupation", "unemployed", "2023-01-01"),
            _cand("b", "Gina", "occupation", "online store", "2023-06-01"),
        ]
        rels = rules.judge_relations_rules("Where does she work now?", cands)
        assert rels and rels[0]["type"] == "SUPERSEDE"


class TestValidity:
    def test_superseded_old_is_historical(self):
        """BR-11：被替代的旧记忆在本次查询中标记 historical（不回写）。"""
        cands = [
            _cand("old", "Gina", "occupation", "unemployed", "2023-01-01", score=0.8),
            _cand("new", "Gina", "occupation", "store", "2023-06-01", score=0.9),
            _cand("misc", "Jon", "hobby", "painting", "2023-03-01", score=0.7),
        ]
        rels = [
            {"from_memory_id": "old", "to_memory_id": "new", "type": "SUPERSEDE",
             "reason": "r", "evidence_memory_ids": ["old", "new"]},
        ]
        items = rules.resolve_validity_rules(cands, rels)
        by_id = {i["memory_id"]: i for i in items}
        assert by_id["old"]["status"] == "historical"
        assert by_id["new"]["status"] == "effective"
        assert by_id["misc"]["status"] == "effective"

    def test_conflict_keeps_both_sides(self):
        """BR-06：冲突双方均保留并标记 conflict。"""
        cands = [
            _cand("x", "Gina", "age", "25", "2023-01-01"),
            _cand("y", "Gina", "age", "30", "2023-01-01"),
        ]
        rels = [{"from_memory_id": "x", "to_memory_id": "y", "type": "CONFLICT",
                 "reason": "r", "evidence_memory_ids": ["x", "y"]}]
        items = rules.resolve_validity_rules(cands, rels)
        assert all(i["status"] == "conflict" for i in items)

    def test_low_score_irrelevant(self):
        """低于阈值 → irrelevant，附理由。"""
        cands = [_cand("weak", "Jon", "hobby", "chess", "2023-01-01", score=0.01)]
        items = rules.resolve_validity_rules(cands, [], irrelevant_score_threshold=0.05)
        assert items[0]["status"] == "irrelevant"

    def test_retain_both_effective(self):
        cands = [
            _cand("a", "Gina", "pet", "dog", "2023-01-01"),
            _cand("b", "Gina", "pet", "dog", "2023-05-01"),
        ]
        rels = [{"from_memory_id": "a", "to_memory_id": "b", "type": "RETAIN",
                 "reason": "r", "evidence_memory_ids": []}]
        items = rules.resolve_validity_rules(cands, rels)
        assert all(i["status"] == "effective" for i in items)
