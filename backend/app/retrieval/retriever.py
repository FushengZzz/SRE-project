# -*- coding: utf-8 -*-
"""B4 · 候选检索（FR-07 / FR-08 / BR-08 / BR-09）。

- TF-IDF + 余弦相似度（M4 版方案；向量检索升级留待 Phase 2）；
- 每次仅对单一对话的完整记忆集合建模，结果不跨对话（AT-08）；
- 显式 as_of 截止：晚于截止的来源会话不得进入候选（BR-09）；
- 默认当前 = 对话可用历史的末端（最后一个「有轮次」会话的时间），
  绝不使用运行机器日期（BR-08）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from ..database import Database, row_to_memory
from ..errors import InvalidParamError, NotFoundError
from ..models import Memory, MemoryWithScore, SourceRef

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _SKLEARN_OK = True
except Exception:  # pragma: no cover - 环境缺失时降级为顺序返回
    _SKLEARN_OK = False


def parse_as_of(value: str) -> datetime:
    """解析显式截止条件：ISO 日期或日期时间。无效即拒绝（FR-07）。"""
    v = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    raise InvalidParamError(
        f"as_of 无法解析：{value!r}（请使用 ISO 格式，如 2023-10-01 或 2023-10-01T12:00:00）")


def available_history_end(db: Database, conversation_id: str) -> Optional[str]:
    """对话可用历史末端 = 最后一个有轮次会话的标准时间（BR-08）。

    注意：LoCoMo 中存在仅有日期、无轮次的"未来"会话（如 conv-26 的
    session_20+），它们不属于可用历史，绝不能当作历史末端。
    """
    row = db.query_one(
        "SELECT MAX(parsed_time) AS t FROM sessions "
        "WHERE conversation_id=? AND has_turns=1 AND parsed_time IS NOT NULL",
        (conversation_id,),
    )
    return row["t"] if row and row["t"] else None


def _row_to_memory_model(row: Any) -> Memory:
    d = row_to_memory(row)
    d["sources"] = [SourceRef(**s) for s in d["sources"]]
    return Memory.model_validate(d)


class Retriever:
    """按对话构建 TF-IDF 索引并检索候选记忆。"""

    def __init__(self, db: Database):
        self.db = db
        # conversation_id -> (vectorizer, matrix, memory_ids, count) 的进程内缓存
        self._cache: dict[str, tuple[Any, Any, list[str], int]] = {}

    # ------------------------------------------------------------------
    def retrieve(
        self,
        conversation_id: str,
        question: str,
        *,
        as_of: Optional[str] = None,
        top_k: int = 5,
    ) -> tuple[list[MemoryWithScore], Optional[str], int]:
        """检索候选记忆。

        返回 (按分数降序的候选, 实际截止时间, as_of 过滤后的候选总数)。
        top_k 大于总数时返回实际数量（AT-08）。
        """
        conv = self.db.query_one(
            "SELECT conversation_id FROM conversations WHERE conversation_id=?",
            (conversation_id,),
        )
        if conv is None:
            raise NotFoundError(f"对话不存在：{conversation_id}")

        rows = self.db.query(
            "SELECT * FROM memories WHERE conversation_id=?", (conversation_id,))
        if not rows:
            raise NotFoundError(
                f"对话 {conversation_id} 尚未构建记忆（请先执行构建任务）")

        # 截止过滤（BR-09）：仅保留 session_time 不晚于截止的记忆；
        # 会话时间未知的记忆在显式截止下无法证明早于截止，保守排除。
        default_cutoff = available_history_end(self.db, conversation_id)
        effective_cutoff = as_of or default_cutoff
        if as_of:
            as_of_dt = parse_as_of(as_of)
            filtered = [
                r for r in rows
                if r["session_time"] and datetime.fromisoformat(r["session_time"]) <= as_of_dt
            ]
        else:
            filtered = list(rows)

        candidates = self._rank(question, filtered, top_k)
        return candidates, effective_cutoff, len(filtered)

    # ------------------------------------------------------------------
    def _rank(self, question: str, rows: list[Any], top_k: int) -> list[MemoryWithScore]:
        """TF-IDF 排序；无法建模时按导入顺序回退（分数 0）。"""
        if not rows:
            return []
        if not _SKLEARN_OK or len(rows) == 0:
            return self._fallback(rows, top_k)

        try:
            vec, matrix, ids, _ = self._get_index(rows)
        except Exception:
            return self._fallback(rows, top_k)

        # 过滤子集在索引中的行号
        id_to_row: dict[str, int] = {mid: i for i, mid in enumerate(ids)}
        positions = [id_to_row[r["memory_id"]] for r in rows if r["memory_id"] in id_to_row]
        if not positions:
            return self._fallback(rows, top_k)

        q_vec = vec.transform([question])
        sims = cosine_similarity(q_vec, matrix[positions])[0]
        scored = list(zip(rows, [float(x) for x in sims]))
        scored.sort(key=lambda x: (-x[1], x[0]["memory_id"]))
        result: list[MemoryWithScore] = []
        for row, score in scored[: top_k]:
            mem = _row_to_memory_model(row)
            result.append(MemoryWithScore(memory=mem, score=round(min(max(score, 0.0), 1.0), 6)))
        return result

    def _fallback(self, rows: list[Any], top_k: int) -> list[MemoryWithScore]:
        return [
            MemoryWithScore(memory=_row_to_memory_model(r), score=0.0)
            for r in rows[:top_k]
        ]

    def _get_index(self, rows: list[Any]) -> tuple[Any, Any, list[str], int]:
        """会话级 TF-IDF 索引（按对话缓存，记忆数变化时重建）。"""
        # 用任一行的 conversation_id（同一对话）
        conv_id = rows[0]["conversation_id"]
        all_rows = self.db.query(
            "SELECT memory_id, content FROM memories WHERE conversation_id=?", (conv_id,))
        ids = [r["memory_id"] for r in all_rows]
        contents = [r["content"] for r in all_rows]
        cached = self._cache.get(conv_id)
        if cached is not None and cached[3] == len(all_rows):
            return cached[0], cached[1], cached[2], cached[3]

        if not contents:
            raise ValueError("empty index")
        vec = TfidfVectorizer(stop_words="english", lowercase=True)
        matrix = vec.fit_transform(contents)
        self._cache[conv_id] = (vec, matrix, ids, len(all_rows))
        return vec, matrix, ids, len(all_rows)
