# -*- coding: utf-8 -*-
"""导入与构建测试：AT-01（导入一致 / 重复导入）、AT-02（校验定位）、
AT-03（抽取可回溯）、AT-04（重试不重复写入）。"""
from __future__ import annotations

import json
from pathlib import Path

from app.data.importer import import_dataset
from app.database import get_database
from app.memory.builder import create_build_task, run_build_task

from .conftest import FIXTURE_T1, FIXTURE_T2


def _imported_counts(db, cid: str) -> tuple[int, int, int]:
    sess = db.query_one(
        "SELECT COUNT(*) AS n FROM sessions WHERE conversation_id=? AND has_turns=1", (cid,))
    turns = db.query_one("SELECT COUNT(*) AS n FROM turns WHERE conversation_id=?", (cid,))
    mems = db.query_one("SELECT COUNT(*) AS n FROM memories WHERE conversation_id=?", (cid,))
    return sess["n"], turns["n"], mems["n"]


def test_import_counts_and_manifest(db):
    """AT-01：来源与轮次数一致，数据清单记录来源摘要。"""
    report = import_dataset(db, str(FIXTURE_T1))
    assert report.imported == ["conv-t1"]
    assert not report.rejected and not report.errors
    s, t, _ = _imported_counts(db, "conv-t1")
    assert (s, t) == (4, 11)  # 4 个会话、11 轮

    manifest = db.query_one("SELECT * FROM dataset_manifest ORDER BY id")
    assert manifest["file_sha256"] == report.file_sha256
    assert json.loads(manifest["conversation_ids"]) == ["conv-t1"]


def test_duplicate_import_no_duplicates(db):
    """AT-01：重复导入同一数据版本不得静默产生重复记录。"""
    import_dataset(db, str(FIXTURE_T1))
    report2 = import_dataset(db, str(FIXTURE_T1))
    assert report2.skipped == ["conv-t1"]
    assert report2.imported == []
    s, t, _ = _imported_counts(db, "conv-t1")
    assert (s, t) == (4, 11)


def test_invalid_dia_id_located(tmp_path, db):
    """AT-02：dia_id 不符被准确定位，不产生假成功。"""
    bad = json.loads(FIXTURE_T1.read_text(encoding="utf-8"))
    bad[0]["conversation"]["session_1"][1]["dia_id"] = "D9:9"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    report = import_dataset(db, str(p))
    assert report.rejected == ["conv-t1"]
    assert report.imported == []
    err = report.errors[0]
    assert "session_1" in err.location and "dia_id" in err.message


def test_missing_sample_id_located(tmp_path, db):
    """AT-02：缺 sample_id 被记录位置。"""
    bad = [{"conversation": {}}]
    p = tmp_path / "bad2.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    report = import_dataset(db, str(p))
    assert report.imported == [] and report.rejected == []
    assert "sample_id" in report.errors[0].message


def test_build_and_traceability(db):
    """AT-03：抽取记忆必填完整、证据全部可回溯。"""
    import_dataset(db, str(FIXTURE_T1))
    status = create_build_task(db, "conv-t1")
    final = run_build_task(db, status.task_id)
    assert final.status == "completed"
    assert final.success_count > 0

    rows = db.query("SELECT * FROM memories WHERE conversation_id='conv-t1'")
    assert rows
    for r in rows:
        assert r["content"].strip()
        assert r["record_status"] in ("ready", "needs_review")
        for src in json.loads(r["sources"]):
            hit = db.query_one(
                "SELECT turn_id FROM turns WHERE conversation_id=? AND session_id=? AND turn_id=?",
                ("conv-t1", src["session_id"], src["turn_id"]),
            )
            assert hit is not None, "证据必须可回溯到原始轮次"


def test_retry_build_no_duplicate_writes(db):
    """AT-04：重复构建不重复写入已完成记忆。"""
    import_dataset(db, str(FIXTURE_T1))
    st1 = create_build_task(db, "conv-t1")
    f1 = run_build_task(db, st1.task_id)
    n1 = _imported_counts(db, "conv-t1")[2]

    st2 = create_build_task(db, "conv-t1")
    f2 = run_build_task(db, st2.task_id)
    n2 = _imported_counts(db, "conv-t1")[2]
    assert f2.status == "completed"
    assert f2.success_count == 0  # 会话级跳过 → 0 新写入
    assert n1 == n2


def test_partial_failure_is_visible(db, monkeypatch):
    """AT-04：注入模型失败 → 任务失败可见、错误摘要含会话定位。"""
    import_dataset(db, str(FIXTURE_T1))

    from app.llm.client import MockLLMClient

    class Boom(MockLLMClient):
        def chat_json(self, **kwargs):
            raise RuntimeError("injected model failure")

    st = create_build_task(db, "conv-t1")
    final = run_build_task(db, st.task_id, client=Boom(None))
    assert final.status == "failed"
    assert final.failed_count == final.progress_total
    assert "session 1" in (final.error_summary or "")
    # 失败会话不写完成标记，也不产生记忆
    assert _imported_counts(db, "conv-t1")[2] == 0
