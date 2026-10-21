# -*- coding: utf-8 -*-
"""API 端到端冒烟：UC-02 / UC-03 全链路 + AT-05 / AT-07 / AT-08 级验收。"""
from __future__ import annotations

import json

from .conftest import FIXTURE_T1, FIXTURE_T2


def _get(client, path, **kw):
    r = client.get(path, **kw)
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client):
    data = _get(client, "/api/health")
    assert data["llm_provider"] == "mock"


def test_conversations_listed(client):
    convs = _get(client, "/api/conversations")
    assert {c["conversation_id"] for c in convs} == {"conv-t1", "conv-t2"}
    for c in convs:
        assert c["memory_count"] > 0 and c["turn_count"] > 0


def test_memory_browse_filter_pagination(client):
    """AT-06 相关：筛选、分页、实体过滤。"""
    all_items = _get(client, "/api/memories?conversation_id=conv-t1&page_size=50")
    assert all_items["total"] == 7  # 迷你数据集的第一人称陈述数

    paged = _get(client, "/api/memories?conversation_id=conv-t1&page=1&page_size=2")
    assert len(paged["items"]) == 2 and paged["has_more"] is True

    gina = _get(client, "/api/memories?conversation_id=conv-t1&entity=Gina&page_size=50")
    assert all(m["entity"] == "Gina" for m in gina["items"])

    kw = _get(client, "/api/memories?conversation_id=conv-t1&keyword=DoorDash")
    assert kw["total"] >= 1

    empty = _get(client, "/api/memories?conversation_id=conv-t1&keyword=zzz-not-exist")
    assert empty["total"] == 0 and empty["items"] == []


def test_evidence_trace(client):
    """AT-06/FR-06：证据回溯到原始轮次与原文。"""
    items = _get(client, "/api/memories?conversation_id=conv-t1&page_size=50")["items"]
    m = items[0]
    ev = _get(client, f"/api/memories/{m['memory_id']}/evidence")
    assert ev["memory"]["memory_id"] == m["memory_id"]
    assert ev["sources"], "多来源为空"
    for s in ev["sources"]:
        assert s["speaker"] and s["text"]
        assert s["session_raw_time"]  # 会话时间信息

    turn = _get(client, "/api/turns/conv-t1/D1:2")
    assert "DoorDash" in turn["text"]

    r = client.get("/api/turns/conv-t1/D99:1")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_query_supersede_chain(client):
    """AT-10 相关：查询语义下新状态替代旧状态 → SUPERSEDE + 有效性解析。"""
    mems = _get(client, "/api/memories?conversation_id=conv-t1&entity=Gina&page_size=50")["items"]
    occ = [m for m in mems if m["attribute"] == "occupation"]
    assert len(occ) == 2
    old = min(occ, key=lambda m: m["session_time"])   # unemployed（session 1）
    new = max(occ, key=lambda m: m["session_time"])   # online store（session 4）

    r = client.post("/api/query", json={
        "conversation_id": "conv-t1",
        "question": "What is Gina's occupation now?",
        "top_k": 20,
    })
    assert r.status_code == 200, r.text
    data = r.json()

    # 候选均来自 conv-t1（不跨对话，AT-08）
    assert all(c["memory"]["conversation_id"] == "conv-t1" for c in data["candidates"])
    # 默认截止 = 最后有轮次会话（BR-08）
    assert data["effective_cutoff"] == "2023-06-30T16:45:00"

    sup = [x for x in data["relations"] if x["type"] == "SUPERSEDE"]
    assert len(sup) == 1
    assert sup[0]["from_memory_id"] == old["memory_id"]
    assert sup[0]["to_memory_id"] == new["memory_id"]
    assert sup[0]["reason"]

    by_id = {v["memory_id"]: v for v in data["validity"]}
    assert by_id[old["memory_id"]]["status"] == "historical"
    assert by_id[new["memory_id"]]["status"] == "effective"

    # 答案与引用
    assert data["answer"]["status"] == "answered"
    assert set(data["answer"]["cited_memory_ids"]) <= set(data["effective_memory_ids"])

    # 查询结果可回查
    q = _get(client, f"/api/query/{data['query_id']}")
    assert q["question"] == "What is Gina's occupation now?"


def test_gina_work_change_preset_supersede(client):
    """Gina「工作变化」preset：显式问失业与开店，应召回 occupation 并判定 SUPERSEDE。"""
    r = client.post("/api/query", json={
        "conversation_id": "conv-t1",
        "question": "Did Gina lose her job and open an online clothing store?",
        "top_k": 20,
    })
    assert r.status_code == 200, r.text
    data = r.json()

    assert any(
        candidate["memory"]["attribute"] == "occupation"
        for candidate in data["candidates"]
    )
    supersede = [rel for rel in data["relations"] if rel["type"] == "SUPERSEDE"]
    assert len(supersede) >= 1
    assert data["answer"]["status"] == "answered"
    assert set(data["answer"]["cited_memory_ids"]) <= set(data["effective_memory_ids"])


def test_query_update_chain(client):
    """AT-09：同一过程阶段推进 → UPDATE 链（researching → applied → passed）。"""
    r = client.post("/api/query", json={
        "conversation_id": "conv-t1",
        "question": "How is Gina's adoption progress?",
        "top_k": 20,
    })
    data = r.json()
    ups = [x for x in data["relations"] if x["type"] == "UPDATE"]
    assert len(ups) == 2
    ids = [x["from_memory_id"] for x in ups] + [ups[-1]["to_memory_id"]]
    mems = {m["memory_id"]: m for m in _get(
        client, "/api/memories?conversation_id=conv-t1&entity=Gina&page_size=50")["items"]}
    times = [mems[i]["session_time"] for i in ids]
    assert times == sorted(times), "UPDATE 链必须按时间旧 → 新"


def test_as_of_cutoff(client):
    """BR-09：显式截止过滤晚于截止的来源，实际截止回显。"""
    r = client.post("/api/query", json={
        "conversation_id": "conv-t1",
        "question": "What is Gina's occupation?",
        "as_of": "2023-03-31",
        "top_k": 20,
    })
    data = r.json()
    assert data["effective_cutoff"] == "2023-03-31"
    assert data["candidates"]
    for c in data["candidates"]:
        assert c["memory"]["session_time"] <= "2023-03-31"


def test_insufficient_evidence(client):
    """FR-11 / BR-12：无证据 → insufficient_evidence，不编造。"""
    r = client.post("/api/query", json={
        "conversation_id": "conv-t2",
        "question": "What is the capital of France?",
    })
    data = r.json()
    assert data["answer"]["status"] == "insufficient_evidence"
    assert data["effective_memory_ids"] == []
    assert not data["answer"]["cited_memory_ids"]


def test_k_larger_than_total_ok(client):
    """AT-08：K 大于总数不报错，返回实际数量。"""
    r = client.post("/api/query", json={
        "conversation_id": "conv-t2",
        "question": "What hobby did Alice start?",
        "top_k": 100,
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["candidates"]) < 100


def test_invalid_query_params(client):
    """AT-07：空问题 / 非法 K / 未知对话 → 明确错误（code 可区分）。"""
    r1 = client.post("/api/query", json={"conversation_id": "conv-t1", "question": "   "})
    assert r1.status_code == 400
    e1 = r1.json()["error"]
    assert e1["code"] == "validation_error" and e1["request_id"]

    r2 = client.post("/api/query", json={
        "conversation_id": "conv-t1", "question": "q?", "top_k": 0})
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "validation_error"

    r3 = client.post("/api/query", json={
        "conversation_id": "conv-nope", "question": "q?"})
    assert r3.status_code == 404
    assert r3.json()["error"]["code"] == "not_found"

    r4 = client.post("/api/query", json={
        "conversation_id": "conv-t1", "question": "q?", "as_of": "not-a-date"})
    assert r4.status_code == 400
    assert "as_of" in r4.json()["error"]["message"]


def test_unbuilt_conversation_rejected(isolated_env):
    """AT-07：导入但未构建的对话查询 → 明确错误。"""
    from fastapi.testclient import TestClient

    from app.config import reset_settings
    from app.data.importer import import_dataset
    from app.database import get_database
    from app.main import create_app

    db = get_database()
    import_dataset(db, str(FIXTURE_T1))
    db.close()
    reset_settings()
    with TestClient(create_app()) as c:
        r = c.post("/api/query", json={"conversation_id": "conv-t1", "question": "hi?"})
        assert r.status_code == 404
        assert "尚未构建" in r.json()["error"]["message"]


def test_export_parseable_and_unique(client):
    """AT-05：导出可解析、范围正确、ID 唯一、来源引用完整。"""
    r = client.post("/api/export", json={"conversation_id": "conv-t1"})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    payload = json.loads(r.content.decode("utf-8"))

    assert payload["schema_version"] == "0.1"
    assert payload["conversation_id"] == "conv-t1"
    ids = [m["memory_id"] for m in payload["memories"]]
    assert len(ids) == payload["memory_count"] == len(set(ids))
    turn_ids = set()
    for m in payload["memories"]:
        for s in m["sources"]:
            turn_ids.add((s["session_id"], s["turn_id"]))
    # 引用完整：每个来源轮次真实存在
    for sid, tid in turn_ids:
        t = client.get(f"/api/turns/conv-t1/{tid}")
        assert t.status_code == 200

    # 全量导出（含两段对话）
    r2 = client.post("/api/export", json={})
    payload2 = json.loads(r2.content.decode("utf-8"))
    assert payload2["conversation_id"] is None
    assert payload2["memory_count"] > payload["memory_count"]


def test_eval_placeholder(client):
    """FR-13：批量评测 Phase 2 占位。"""
    r = client.post("/api/eval/run", json={})
    assert r.status_code == 501
    assert r.json()["error"]["code"] == "not_implemented"


def test_import_and_build_via_api(isolated_env):
    """API 路径完整走通：导入 → 构建 → 轮询任务。"""
    from fastapi.testclient import TestClient

    from app.config import reset_settings
    from app.main import create_app

    reset_settings()
    with TestClient(create_app()) as c:
        r = c.post("/api/import", json={"file_path": str(FIXTURE_T1)})
        assert r.status_code == 200, r.text
        report = r.json()
        assert report["imported"] == ["conv-t1"]

        # 重复导入：跳过不重复（FR-01）
        r2 = c.post("/api/import", json={"file_path": str(FIXTURE_T1)})
        assert r2.json()["skipped"] == ["conv-t1"]

        b = c.post("/api/build", json={"conversation_id": "conv-t1"})
        assert b.status_code == 200, b.text
        task = b.json()
        st = c.get(f"/api/build/{task['task_id']}")
        final = st.json()
        assert final["status"] == "completed"
        assert final["success_count"] > 0
        assert final["progress_done"] == final["progress_total"]

        mems = c.get("/api/memories?conversation_id=conv-t1")
        assert mems.json()["total"] == final["success_count"]
