# -*- coding: utf-8 -*-
"""pytest 公共夹具：独立数据库 + mock provider + 迷你数据集。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

FIXTURE_T1 = Path(__file__).parent / "fixtures" / "mini_locomo.json"
FIXTURE_T2 = Path(__file__).parent / "fixtures" / "mini_locomo_t2.json"


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """每个测试独立数据库与导出目录，强制 mock provider。"""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    from app.config import reset_settings

    reset_settings()
    yield tmp_path
    reset_settings()


@pytest.fixture()
def client(isolated_env):
    """已导入并构建好两段迷你对话的 API 客户端。"""
    from fastapi.testclient import TestClient

    from app.config import reset_settings, get_settings
    from app.data.importer import import_dataset
    from app.database import get_database
    from app.main import create_app
    from app.memory.builder import create_build_task, run_build_task

    db = get_database()
    try:
        import_dataset(db, str(FIXTURE_T1))
        import_dataset(db, str(FIXTURE_T2))
        for cid in ("conv-t1", "conv-t2"):
            status = create_build_task(db, cid)
            run_build_task(db, status.task_id)
    finally:
        db.close()
    reset_settings()  # 让路由内 get_settings 重新读取（含 env 变更）
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(isolated_env):
    """独立数据库连接（供服务层直接调用）。"""
    from app.database import get_database

    conn = get_database()
    yield conn
    conn.close()
