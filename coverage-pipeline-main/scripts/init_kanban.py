#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""init_kanban.py - 初始化覆盖率 Kanban board

在测试电脑上执行:
  python scripts/init_kanban.py [--build-server 192.168.242.120] [--test-pc-id test-pc1]
"""
import argparse
import json
import os
from datetime import datetime

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-server", default="192.168.242.120")
    parser.add_argument("--test-pc-id", default="test-pc1")
    parser.add_argument("--board-dir", default="D:/通信模组/at_kb_runs")
    args = parser.parse_args()

    print(f"Kanban Board 初始化")
    print(f"  Board 目录: {args.board_dir}")
    print(f"  编译服务器: {args.build_server}")
    print(f"  测试电脑: {args.test_pc_id}")

    board_state = {
        "created_at": datetime.now().isoformat(),
        "build_server": args.build_server,
        "test_pcs": [args.test_pc_id],
        "tasks": [],
    }
    with open(os.path.join(args.board_dir, "board_state.json"), "w") as f:
        json.dump(board_state, f, indent=2)

    build_status = {
        "firmware": None, "module": None, "stubs": 0,
        "timestamp": None, "status": "idle",
    }
    with open(os.path.join(args.board_dir, "build_status.json"), "w") as f:
        json.dump(build_status, f, indent=2)

    print("初始化完成")

if __name__ == "__main__":
    main()
