# -*- coding: utf-8 -*-
"""命令行导入数据（UC-01）。

用法（在 backend/ 目录下）：
    python scripts/import_data.py --file ../data/raw/locomo10.json
    python scripts/import_data.py --file ../data/raw/locomo10.json \
        --version locomo10-202610 --dev "conv-26,conv-30,conv-41,conv-42" --test "conv-43,conv-44"

说明：
- 6 段对话的官方划分名单待课程确认（SRS 3.1），--dev/--test 仅为可配置占位；
- 重复导入会跳过已存在的对话（不产生重复记录，FR-01）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.config import get_settings          # noqa: E402
from app.database import get_database        # noqa: E402
from app.data.importer import import_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 LoCoMo 数据文件")
    parser.add_argument("--file", required=True, help="数据文件路径（locomo10.json）")
    parser.add_argument("--version", default=None, help="数据版本标识")
    parser.add_argument("--dev", default=None, help="dev 对话 ID 列表（逗号分隔，可选）")
    parser.add_argument("--test", default=None, help="test 对话 ID 列表（逗号分隔，可选）")
    args = parser.parse_args()

    dev = [x.strip() for x in args.dev.split(",") if x.strip()] if args.dev else None
    test = [x.strip() for x in args.test.split(",") if x.strip()] if args.test else None

    db = get_database()
    try:
        report = import_dataset(
            db, args.file,
            dataset_version=args.version,
            dev_conversations=dev,
            test_conversations=test,
        )
    finally:
        db.close()

    print(f"数据版本   : {report.dataset_version}")
    print(f"文件摘要   : {report.file_sha256[:16]}…")
    print(f"导入对话   : {report.imported}")
    print(f"跳过(已存在): {report.skipped}")
    print(f"拒绝(校验失败): {report.rejected}")
    print(f"会话/轮次/QA: {report.session_count} / {report.turn_count} / {report.qa_count}")
    if report.errors:
        print("\n校验错误明细：")
        for e in report.errors:
            print(f"  [{e.conversation_id}] {e.location}: {e.message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
