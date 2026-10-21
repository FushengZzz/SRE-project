# -*- coding: utf-8 -*-
"""从 LoCoMo 原始文件生成演示子集，避免把未分配的对话导入开发库。

用法（在 backend/ 目录下）：
    python scripts/make_demo_subset.py
    python scripts/make_demo_subset.py --conversations conv-26,conv-30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 LoCoMo 演示子集")
    parser.add_argument(
        "--source",
        default="../data/raw/locomo10.json",
        help="原始 LoCoMo 文件路径",
    )
    parser.add_argument(
        "--output",
        default="data/demo_locomo.json",
        help="输出文件路径",
    )
    parser.add_argument(
        "--conversations",
        default="conv-26,conv-30",
        help="要保留的对话 ID，逗号分隔",
    )
    args = parser.parse_args()

    wanted = {item.strip() for item in args.conversations.split(",") if item.strip()}
    source = Path(args.source)
    if not source.is_file():
        print(f"源文件不存在：{source}", file=sys.stderr)
        return 1

    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("源文件顶层应为数组", file=sys.stderr)
        return 1

    subset = [item for item in data if item.get("sample_id") in wanted]
    found = {item["sample_id"] for item in subset}
    missing = wanted - found
    if missing:
        print(f"源文件中缺少对话：{sorted(missing)}", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(subset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已写入 {output}：{', '.join(sorted(found))}，共 {len(subset)} 段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
