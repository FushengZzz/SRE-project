# -*- coding: utf-8 -*-
"""B2 · 记忆构建任务（FR-03）。

- 会话级批量抽取，逐会话提交进度（阶段 / 进度 / 成功失败数 / 错误摘要）；
- 会话级完成标记 + 确定性 memory_id 双重保证：重试不重复写入已完成记忆；
- 单会话失败不中断整体，最终状态明确标识 completed / partial_failed / failed；
- 不能把部分输出冒充完整集合（UC-01 后置）。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from ..config import Settings, get_settings
from ..database import Database
from ..errors import InvalidParamError, NotFoundError
from ..llm.client import LLMClient, get_llm_client
from ..models import BuildTaskStatus
from .extractor import extract_session_memories


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_build_task(
    db: Database,
    conversation_id: str,
    *,
    force: bool = False,
    settings: Settings | None = None,
) -> BuildTaskStatus:
    """创建构建任务（pending），实际执行由 run_build_task 完成。"""
    s = settings or get_settings()
    row = db.query_one(
        "SELECT conversation_id FROM conversations WHERE conversation_id=?",
        (conversation_id,),
    )
    if row is None:
        raise NotFoundError(f"对话不存在：{conversation_id}（请先导入数据）")

    session_rows = db.query(
        "SELECT session_id FROM sessions WHERE conversation_id=? AND has_turns=1 "
        "ORDER BY CAST(session_id AS INTEGER)",
        (conversation_id,),
    )
    if not session_rows:
        raise InvalidParamError(f"对话 {conversation_id} 没有带轮次的会话")

    task_id = uuid4().hex[:12]
    now = _now()
    config = {
        "llm_provider": s.llm_provider,
        "llm_model": s.llm_model,
        "extract_prompt_version": s.extract_prompt_version,
        "force": force,
    }
    with db.transaction():
        db.execute(
            "INSERT INTO build_tasks (task_id, conversation_id, dataset_version, status, "
            "progress_done, progress_total, success_count, failed_count, config_json, created_at, updated_at) "
            "VALUES (?,?,?,?,0,?,0,0,?,?,?)",
            (task_id, conversation_id, _conversation_version(db, conversation_id),
             "pending", len(session_rows), json.dumps(config, ensure_ascii=False), now, now),
        )
    return get_build_status(db, task_id)


def _conversation_version(db: Database, conversation_id: str) -> str | None:
    row = db.query_one(
        "SELECT dataset_version FROM conversations WHERE conversation_id=?",
        (conversation_id,),
    )
    return row["dataset_version"] if row else None


def run_build_task(
    db: Database,
    task_id: str,
    *,
    settings: Settings | None = None,
    client: LLMClient | None = None,
) -> BuildTaskStatus:
    """同步执行构建任务（API 层可放入后台线程，CLI 直接调用）。

    幂等保证：
    1. build_session_status 已 completed 的会话跳过（除非 force 或上次失败）；
    2. memory_id 内容寻址 + INSERT OR IGNORE，重复写入被忽略。
    """
    s = settings or get_settings()
    task = db.query_one("SELECT * FROM build_tasks WHERE task_id=?", (task_id,))
    if task is None:
        raise NotFoundError(f"构建任务不存在：{task_id}")

    conversation_id = task["conversation_id"]
    force = bool(json.loads(task["config_json"] or "{}").get("force", False))
    llm = client or get_llm_client(s)

    now = _now()
    db.execute("UPDATE build_tasks SET status='running', updated_at=? WHERE task_id=?",
               (now, task_id))
    db.conn.commit()

    sessions = db.query(
        "SELECT session_id, raw_time, parsed_time FROM sessions "
        "WHERE conversation_id=? AND has_turns=1 ORDER BY CAST(session_id AS INTEGER)",
        (conversation_id,),
    )
    errors: list[str] = []
    done = success = failed = 0
    total = len(sessions)

    for sess in sessions:
        sid = sess["session_id"]
        done_before = db.query_one(
            "SELECT status FROM build_session_status WHERE conversation_id=? AND session_id=?",
            (conversation_id, sid),
        )
        if (not force and done_before is not None
                and done_before["status"] == "completed"):
            # 该会话此前已成功，跳过（FR-03：重试不重复写入已完成记忆）
            done += 1
            _update_progress(db, task_id, done, total, success, failed)
            continue

        turns = db.query(
            "SELECT turn_id, turn_no, speaker, text FROM turns "
            "WHERE conversation_id=? AND session_id=? ORDER BY turn_no",
            (conversation_id, sid),
        )
        session_payload = {
            "session_id": sid,
            "raw_time": sess["raw_time"],
            "parsed_time": sess["parsed_time"],
            "turns": [dict(t) for t in turns],
        }
        try:
            memories, item_errors = extract_session_memories(
                llm,
                conversation_id=conversation_id,
                session=session_payload,
                task_id=task_id,
            )
        except Exception as e:  # 模型不可用 / 超时 / 输出畸形：会话级失败
            errors.append(f"session {sid}: {e}")
            failed += 1
            _set_session_status(db, conversation_id, sid, "failed", 0, task_id)
            done += 1
            _update_progress(db, task_id, done, total, success, failed, errors)
            continue

        written = _write_memories(db, memories, task_id)
        success += written
        if item_errors:
            # 单条候选被丢弃计入失败数，会话仍视为完成但任务最终为 partial
            failed += len(item_errors)
            errors.extend(f"session {sid}: {msg}" for msg in item_errors)
        _set_session_status(db, conversation_id, sid, "completed", written, task_id)
        done += 1
        _update_progress(db, task_id, done, total, success, failed, errors)

    # 汇总状态：0 失败 → completed；全部会话失败 → failed；其余 → partial_failed
    if failed == 0:
        status = "completed"
    elif success == 0 and done >= total:
        status = "failed"
    else:
        status = "partial_failed"
    summary = "\n".join(errors[:20]) or None
    db.execute(
        "UPDATE build_tasks SET status=?, failed_count=?, error_summary=?, updated_at=? "
        "WHERE task_id=?",
        (status, failed, summary, _now(), task_id),
    )
    db.conn.commit()
    return get_build_status(db, task_id)


def _write_memories(db: Database, memories: list[dict[str, Any]], task_id: str) -> int:
    """写入记忆（内容寻址 ID，upsert 幂等：重试/重抽取不产生重复行，
    force 重抽取时刷新字段）。返回写入（含更新）条数。
    """
    written = 0
    with db.transaction():
        for m in memories:
            cur = db.execute(
                "INSERT INTO memories (memory_id, conversation_id, content, entity, "
                "attribute, value, session_time, time_expression, event_time, sources, "
                "record_status, build_task_id, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(memory_id) DO UPDATE SET "
                "content=excluded.content, entity=excluded.entity, "
                "attribute=excluded.attribute, value=excluded.value, "
                "session_time=excluded.session_time, "
                "time_expression=excluded.time_expression, "
                "event_time=excluded.event_time, sources=excluded.sources, "
                "record_status=excluded.record_status, "
                "build_task_id=excluded.build_task_id",
                (m["memory_id"], m["conversation_id"], m["content"], m["entity"],
                 m["attribute"], m["value"], m["session_time"], m["time_expression"],
                 m["event_time"], json.dumps(m["sources"], ensure_ascii=False),
                 m["record_status"], task_id, _now()),
            )
            written += max(cur, 0)
    return written


def _set_session_status(
    db: Database, conversation_id: str, session_id: str,
    status: str, memory_count: int, task_id: str,
) -> None:
    with db.transaction():
        db.execute(
            "INSERT INTO build_session_status (conversation_id, session_id, status, "
            "memory_count, last_task_id, updated_at) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(conversation_id, session_id) DO UPDATE SET "
            "status=excluded.status, memory_count=excluded.memory_count, "
            "last_task_id=excluded.last_task_id, updated_at=excluded.updated_at",
            (conversation_id, session_id, status, memory_count, task_id, _now()),
        )


def _update_progress(
    db: Database, task_id: str,
    done: int, total: int, success: int, failed: int,
    errors: list[str] | None = None,
) -> None:
    summary = "\n".join(errors[:20]) if errors else None
    with db.transaction():
        db.execute(
            "UPDATE build_tasks SET progress_done=?, progress_total=?, success_count=?, "
            "failed_count=?, error_summary=?, updated_at=? WHERE task_id=?",
            (done, total, success, failed, summary, _now(), task_id),
        )


def get_build_status(db: Database, task_id: str) -> BuildTaskStatus:
    row = db.query_one("SELECT * FROM build_tasks WHERE task_id=?", (task_id,))
    if row is None:
        raise NotFoundError(f"构建任务不存在：{task_id}")
    return BuildTaskStatus(
        task_id=row["task_id"],
        conversation_id=row["conversation_id"],
        status=row["status"],
        progress_done=row["progress_done"],
        progress_total=row["progress_total"],
        success_count=row["success_count"],
        failed_count=row["failed_count"],
        error_summary=row["error_summary"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
