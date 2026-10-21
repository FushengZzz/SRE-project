# -*- coding: utf-8 -*-
"""命令行构建记忆（UC-01 / FR-02 / FR-03）。

用法（在 backend/ 目录下）：
    python scripts/build_memories.py --conversation conv-26
    python scripts/build_memories.py --all                 # 构建全部已导入对话
    python scripts/build_memories.py --conversation conv-26 --force  # 忽略会话级完成标记重新抽取

说明：
- LLM_PROVIDER=mock 无需任何 Key 即可运行（NFR-01）；
- 重试安全：已完成会话自动跳过；memory_id 内容寻址 + INSERT OR IGNORE，
  不重复写入（FR-03）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.config import get_settings                  # noqa: E402
from app.database import get_database                # noqa: E402
from app.memory.builder import create_build_task, run_build_task  # noqa: E402


def build_one(db, conversation_id: str, force: bool) -> int:
    status = create_build_task(db, conversation_id, force=force)
    print(f"[{conversation_id}] 任务 {status.task_id} 开始：{status.progress_total} 个会话")
    final = run_build_task(db, status.task_id)
    print(
        f"[{conversation_id}] 完成：状态={final.status}，"
        f"成功写入记忆={final.success_count}，失败={final.failed_count}"
    )
    if final.error_summary:
        print(final.error_summary)
    return 0 if final.status in ("completed", "partial_failed") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="构建结构化记忆")
    parser.add_argument("--conversation", default=None, help="对话 ID")
    parser.add_argument("--all", action="store_true", help="构建全部已导入对话")
    parser.add_argument("--force", action="store_true",
                        help="忽略会话级完成标记，重新抽取全部会话")
    args = parser.parse_args()

    if not args.conversation and not args.all:
        parser.error("请指定 --conversation <id> 或 --all")

    db = get_database()
    try:
        if args.all:
            rows = db.query("SELECT conversation_id FROM conversations ORDER BY conversation_id")
            if not rows:
                print("没有已导入的对话，请先运行 scripts/import_data.py")
                return 1
            rc = 0
            for r in rows:
                rc |= build_one(db, r["conversation_id"], args.force)
            return rc
        return build_one(db, args.conversation, args.force)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
