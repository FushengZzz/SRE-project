# -*- coding: utf-8 -*-
"""B1 · 数据导入（FR-01）。

- 导入课程 LoCoMo 原始文件，保持会话、轮次、说话人与原文对应；
- 校验重复 ID、必填项及格式；失败时指出记录位置（会话 / 轮次）；
- 重复导入同一数据版本不得静默产生重复记录（已存在即跳过并报告）；
- 只导入对话原文与 gold QA 表（gold 仅评测用，SRS 3.1）；
  event_summary / observation / session_summary 等 gold 标注不导入，
  从物理上保证抽取、检索、推理无法使用它们。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from ..database import Database
from ..errors import InvalidParamError
from ..models import ImportConversationError, ImportReport

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

_TIME_RE = re.compile(
    r"^\s*(\d{1,2}):(\d{2})\s*(am|pm)\s+on\s+(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})\s*$",
    re.IGNORECASE,
)


def parse_session_time(raw: str) -> datetime | None:
    """解析 LoCoMo 会话时间（'1:56 pm on 8 May, 2023'）。

    无法解析返回 None；不猜测补齐（BR-10 精神一致）。
    """
    m = _TIME_RE.match(raw or "")
    if not m:
        return None
    hour, minute, ampm, day, month_name, year = m.groups()
    month = _MONTHS.get(month_name.lower())
    if not month or int(day) > 31:
        return None
    h = int(hour) % 12
    if ampm.lower() == "pm":
        h += 12
    try:
        return datetime(int(year), month, int(day), h, int(minute))
    except ValueError:
        return None


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class _ConversationData:
    """一次通过校验的单段对话解析结果。"""

    def __init__(self) -> None:
        self.conversation_id: str = ""
        self.sessions: list[dict[str, Any]] = []   # 含 turns 的会话
        self.turn_count: int = 0
        self.qa: list[dict[str, Any]] = []


def _parse_one_conversation(
    item: dict[str, Any],
    conv_id: str,
    errors: list[ImportConversationError],
) -> _ConversationData | None:
    """校验并解析单段对话；返回 None 表示校验失败（整段拒绝）。"""

    def fail(location: str, message: str) -> None:
        errors.append(ImportConversationError(
            conversation_id=conv_id, location=location, message=message))

    conv = item.get("conversation")
    if not isinstance(conv, dict):
        fail("conversation", "缺少 conversation 对象")
        return None

    data = _ConversationData()
    data.conversation_id = conv_id

    # 会话发现：session_{i} 与 session_{i}_date_time 交替出现，
    # i 递增直至两者均缺失（LoCoMo 存在仅有日期、无轮次的"未来"会话，
    # 它们不属于可用历史，BR-08 的截止取最后有轮次的会话）。
    i = 1
    while True:
        turns_key = f"session_{i}"
        dt_key = f"{turns_key}_date_time"
        has_turns = turns_key in conv
        has_dt = dt_key in conv
        if not has_turns and not has_dt:
            break
        raw_time = conv.get(dt_key)
        if has_dt and (not isinstance(raw_time, str) or not raw_time.strip()):
            fail(f"session_{i}", "date_time 缺失或为空")
            return None
        parsed = parse_session_time(raw_time) if has_dt else None
        if has_dt and parsed is None:
            fail(f"session_{i}", f"date_time 无法解析：{raw_time!r}")
            return None
        if not has_turns:
            i += 1
            continue

        turns_raw = conv[turns_key]
        if not isinstance(turns_raw, list) or not turns_raw:
            fail(f"session_{i}", "turns 缺失或为空列表")
            return None

        session = {
            "session_id": str(i),
            "raw_time": raw_time,
            "parsed_time": _iso(parsed),
            "turns": [],
        }
        for idx, turn in enumerate(turns_raw, 1):
            if not isinstance(turn, dict):
                fail(f"session_{i}", f"第 {idx} 轮不是对象")
                return None
            speaker = turn.get("speaker")
            text = turn.get("text")
            dia_id = turn.get("dia_id")
            if not speaker or not str(speaker).strip():
                fail(f"session_{i} 第 {idx} 轮", "speaker 缺失")
                return None
            if text is None or not str(text).strip():
                fail(f"session_{i} 第 {idx} 轮", "text 缺失或为空")
                return None
            if not dia_id or not str(dia_id).strip():
                fail(f"session_{i} 第 {idx} 轮", "dia_id 缺失")
                return None
            expected = f"D{i}:{idx}"
            if str(dia_id) != expected:
                fail(
                    f"session_{i} 第 {idx} 轮",
                    f"dia_id 不符：期望 {expected}，实际 {dia_id}",
                )
                return None
            session["turns"].append({
                "turn_no": idx,
                "turn_id": str(dia_id),
                "speaker": str(speaker),
                "text": str(text),
            })
        data.sessions.append(session)
        data.turn_count += len(session["turns"])
        i += 1

    # gold QA：键名允许 answer / adversarial_answer 变体（cat=5 对抗题）
    qa_raw = item.get("qa", [])
    if not isinstance(qa_raw, list):
        fail("qa", "qa 不是数组")
        return None
    for idx, qa in enumerate(qa_raw):
        if not isinstance(qa, dict) or not str(qa.get("question", "")).strip():
            fail(f"qa 第 {idx} 题", "question 缺失")
            return None
        data.qa.append({
            "question": str(qa["question"]),
            "answer": qa.get("answer"),
            "adversarial_answer": qa.get("adversarial_answer"),
            "evidence": json.dumps(qa.get("evidence", []), ensure_ascii=False),
            "category": qa.get("category"),
        })

    if not data.sessions:
        fail("conversation", "没有任何带轮次的会话")
        return None
    return data


def import_dataset(
    db: Database,
    file_path: str,
    *,
    dataset_version: str | None = None,
    dev_conversations: list[str] | None = None,
    test_conversations: list[str] | None = None,
    settings: Settings | None = None,
) -> ImportReport:
    """导入数据文件。返回导入报告（成功 / 跳过 / 拒绝及定位错误）。

    - 同 conversation_id 已存在（任意版本）：跳过并记录，不产生重复（FR-01）；
    - 校验失败：该段对话整体拒绝，其余继续；失败不标记为成功（FR-01）。
    """
    s = settings or get_settings()
    path = Path(file_path)
    if not path.is_file():
        raise InvalidParamError(f"数据文件不存在：{file_path}")

    version = dataset_version or s.dataset_version
    file_sha = _sha256_of_file(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise InvalidParamError(f"数据文件不是合法 UTF-8 JSON：{e}") from e
    if not isinstance(payload, list) or not payload:
        raise InvalidParamError("数据文件顶层应为非空数组（LoCoMo 格式）")

    # 划分：请求参数优先，其次配置（课程名单待确认，SRS 3.1）
    if dev_conversations or test_conversations:
        splits: dict[str, str] = {}
        for cid in (dev_conversations or []):
            splits[cid] = "dev"
        for cid in (test_conversations or []):
            splits.setdefault(cid, "test")
    else:
        splits = {}

    report = ImportReport(dataset_version=version, file_sha256=file_sha)
    parsed_all: list[_ConversationData] = []
    seen_ids: set[str] = set()

    for pos, item in enumerate(payload):
        if not isinstance(item, dict):
            report.errors.append(ImportConversationError(
                conversation_id=f"<index {pos}>",
                location="顶层",
                message="元素不是对象"))
            continue
        conv_id = item.get("sample_id")
        if not conv_id or not str(conv_id).strip():
            report.errors.append(ImportConversationError(
                conversation_id=f"<index {pos}>",
                location="sample_id",
                message="sample_id 缺失"))
            continue
        conv_id = str(conv_id).strip()
        if conv_id in seen_ids:
            report.errors.append(ImportConversationError(
                conversation_id=conv_id,
                location="顶层",
                message=f"文件内重复 conversation_id：{conv_id}"))
            continue
        seen_ids.add(conv_id)

        existing = db.query_one(
            "SELECT dataset_version FROM conversations WHERE conversation_id=?",
            (conv_id,),
        )
        if existing is not None:
            # 已导入（含不同版本）：跳过，绝不静默重复写入（FR-01）
            report.skipped.append(conv_id)
            continue

        parsed = _parse_one_conversation(item, conv_id, report.errors)
        if parsed is None:
            report.rejected.append(conv_id)
        else:
            parsed_all.append(parsed)

    now = datetime.now().isoformat(timespec="seconds")
    imported_ids: list[str] = []
    with db.transaction():
        for data in parsed_all:
            split = splits.get(data.conversation_id) or s.split_of(data.conversation_id)
            db.execute(
                "INSERT INTO conversations (conversation_id, split, dataset_version, imported_at) "
                "VALUES (?,?,?,?)",
                (data.conversation_id, split, version, now),
            )
            for sess in data.sessions:
                db.execute(
                    "INSERT INTO sessions (conversation_id, session_id, raw_time, parsed_time, has_turns) "
                    "VALUES (?,?,?,?,1)",
                    (data.conversation_id, sess["session_id"], sess["raw_time"], sess["parsed_time"]),
                )
                for t in sess["turns"]:
                    db.execute(
                        "INSERT INTO turns (conversation_id, session_id, turn_id, turn_no, speaker, text) "
                        "VALUES (?,?,?,?,?,?)",
                        (data.conversation_id, sess["session_id"], t["turn_id"], t["turn_no"],
                         t["speaker"], t["text"]),
                    )
            for idx, qa in enumerate(data.qa):
                db.execute(
                    "INSERT INTO gold_qa (conversation_id, qa_index, question, answer, "
                    "adversarial_answer, evidence, category) VALUES (?,?,?,?,?,?,?)",
                    (data.conversation_id, idx, qa["question"], qa["answer"],
                     qa["adversarial_answer"], qa["evidence"], qa["category"]),
                )
            imported_ids.append(data.conversation_id)
            report.session_count += len(data.sessions)
            report.turn_count += data.turn_count
            report.qa_count += len(data.qa)

        # 数据清单（SRS 3.1：来源、版本摘要、conversation ID、导入时间）
        db.execute(
            "INSERT INTO dataset_manifest (file_name, file_sha256, dataset_version, imported_at, conversation_ids) "
            "VALUES (?,?,?,?,?)",
            (path.name, file_sha, version, now, json.dumps(imported_ids, ensure_ascii=False)),
        )

    report.imported = imported_ids
    return report
