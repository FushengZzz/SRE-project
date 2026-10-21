# -*- coding: utf-8 -*-
"""SQLite 存储层：连接管理、建表与通用辅助。

设计说明：
- 单用户本地应用（SRS 2.2），采用 SQLite + WAL；每次请求独立连接；
- gold_qa 表仅服务于评测（FR-13，Phase 2），检索、抽取、推理
  代码路径禁止读取该表（SRS 3.1 数据隔离）；
- build_session_status 提供会话级完成标记：配合确定性 memory_id
  双重保证「重试不重复写入已完成记忆」（FR-03）。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id  TEXT PRIMARY KEY,
    split            TEXT NOT NULL DEFAULT 'extra',
    dataset_version  TEXT NOT NULL,
    imported_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    conversation_id  TEXT NOT NULL,
    session_id       TEXT NOT NULL,
    raw_time         TEXT,
    parsed_time      TEXT,
    has_turns        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (conversation_id, session_id)
);

CREATE TABLE IF NOT EXISTS turns (
    conversation_id  TEXT NOT NULL,
    session_id       TEXT NOT NULL,
    turn_id          TEXT NOT NULL,
    turn_no          INTEGER NOT NULL,
    speaker          TEXT NOT NULL,
    text             TEXT NOT NULL,
    PRIMARY KEY (conversation_id, turn_id),
    FOREIGN KEY (conversation_id, session_id)
        REFERENCES sessions (conversation_id, session_id)
);

-- gold 数据（qa）：仅供评测评分，不得进入抽取/检索/推理输入路径（SRS 3.1）
CREATE TABLE IF NOT EXISTS gold_qa (
    conversation_id      TEXT NOT NULL,
    qa_index             INTEGER NOT NULL,
    question             TEXT NOT NULL,
    answer               TEXT,
    adversarial_answer   TEXT,
    evidence             TEXT,
    category             INTEGER,
    PRIMARY KEY (conversation_id, qa_index)
);

CREATE TABLE IF NOT EXISTS memories (
    memory_id        TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL,
    content          TEXT NOT NULL,
    entity           TEXT,
    attribute        TEXT,
    value            TEXT,
    session_time     TEXT,
    time_expression  TEXT,
    event_time       TEXT,
    sources          TEXT NOT NULL,
    record_status    TEXT NOT NULL CHECK (record_status IN ('ready','needs_review')),
    build_task_id    TEXT,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_conv ON memories (conversation_id);

CREATE TABLE IF NOT EXISTS build_tasks (
    task_id          TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL,
    dataset_version  TEXT,
    status           TEXT NOT NULL,
    progress_done    INTEGER NOT NULL DEFAULT 0,
    progress_total   INTEGER NOT NULL DEFAULT 0,
    success_count    INTEGER NOT NULL DEFAULT 0,
    failed_count     INTEGER NOT NULL DEFAULT 0,
    error_summary    TEXT,
    config_json      TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS build_session_status (
    conversation_id  TEXT NOT NULL,
    session_id       TEXT NOT NULL,
    status           TEXT NOT NULL,
    memory_count     INTEGER NOT NULL DEFAULT 0,
    last_task_id     TEXT,
    updated_at       TEXT NOT NULL,
    PRIMARY KEY (conversation_id, session_id)
);

CREATE TABLE IF NOT EXISTS query_results (
    query_id         TEXT PRIMARY KEY,
    conversation_id  TEXT NOT NULL,
    question         TEXT NOT NULL,
    as_of            TEXT,
    created_at       TEXT NOT NULL,
    result_json      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_manifest (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name         TEXT NOT NULL,
    file_sha256       TEXT NOT NULL,
    dataset_version   TEXT NOT NULL,
    imported_at       TEXT NOT NULL,
    conversation_ids  TEXT NOT NULL
);
"""


class Database:
    """SQLite 包装：独立连接 + 常用查询辅助。"""

    def __init__(self, db_file: Path):
        db_file.parent.mkdir(parents=True, exist_ok=True)
        self.db_file = db_file
        self.conn = sqlite3.connect(str(db_file), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """事务：成功提交，异常回滚。"""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        cur = self.conn.execute(sql, params)
        return cur.fetchall()

    def query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        cur = self.conn.execute(sql, params)
        return cur.fetchone()

    def execute(self, sql: str, params: tuple = ()) -> int:
        cur = self.conn.execute(sql, params)
        return cur.rowcount

    def execute_returning_rowid(self, sql: str, params: tuple = ()) -> int:
        cur = self.conn.execute(sql, params)
        return int(cur.lastrowid or 0)


# ---------------------------------------------------------------------------
# 行 → 模型转换辅助
# ---------------------------------------------------------------------------

def row_to_memory(row: sqlite3.Row) -> dict[str, Any]:
    """memories 行 → Memory 模型字段 dict（sources 反序列化）。"""
    d = dict(row)
    d["sources"] = json.loads(d["sources"])
    return d


def sources_to_json(sources: list[dict[str, str]]) -> str:
    return json.dumps(sources, ensure_ascii=False)


def get_database() -> Database:
    """按配置打开数据库（每次调用新连接，由调用方关闭）。"""
    return Database(get_settings().db_file)
