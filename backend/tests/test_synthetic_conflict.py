# -*- coding: utf-8 -*-
"""合成受控用例：同一会话内同属性不同值 → CONFLICT（AT-12 / BR-05）。

该 fixture 不是 LoCoMo 真实数据，只用于验证规则和页面展示；
不得把它当作真实数据分布或评测结果。
"""
from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.data.importer import import_dataset
from app.memory.builder import create_build_task, run_build_task
from app.models import QueryRequest
from app.query_service import run_query

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_conflict.json"
CONVERSATION_ID = "synthetic-conflict-01"


def test_synthetic_conflict_end_to_end(db):
    report = import_dataset(
        db,
        str(FIXTURE),
        dataset_version="synthetic",
        settings=get_settings(),
    )
    assert report.imported == [CONVERSATION_ID]

    status = create_build_task(db, CONVERSATION_ID)
    final = run_build_task(db, status.task_id)
    assert final.status == "completed"

    result = run_query(
        db,
        QueryRequest(
            conversation_id=CONVERSATION_ID,
            question="Alex DoorDash job",
            top_k=10,
        ),
        settings=get_settings(),
    )

    assert len(result.candidates) == 2
    assert [relation.type for relation in result.relations] == ["CONFLICT"]
    assert result.answer.status == "unresolved_conflict"
    assert len(result.conflict_memory_ids) == 2
    assert {item.status for item in result.validity} == {"conflict"}
    assert result.answer.conflict_explanation
