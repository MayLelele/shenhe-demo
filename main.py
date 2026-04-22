#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互式入口：python main.py [--mock]"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from audit_agent.agent import AuditAgent


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="审核辅助 Agent（工具调用 + 记忆 + 反思）")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="无需 OPENAI_API_KEY，本地演示工具链与反思结构",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        help="OpenAI 兼容模型名",
    )
    args = parser.parse_args()

    try:
        agent = AuditAgent(mock=args.mock, model=args.model)
    except ValueError as e:
        print(e, file=sys.stderr)
        print("提示: 使用 python main.py --mock 可离线演示。", file=sys.stderr)
        sys.exit(1)

    sid = agent.session_id
    print(f"会话 ID: {sid}（长期记忆按此 ID 存储）")
    print("输入工单描述或问题，空行退出。示例：")
    print('  用户备注：kyc2提币审  提币金额：100  充值金额：80\n')
    try:
        while True:
            try:
                line = input("你> ").strip()
            except EOFError:
                break
            if not line:
                break
            reply = agent.run_turn(line)
            print(f"Agent> {reply}\n")
    finally:
        agent.close()


if __name__ == "__main__":
    main()
