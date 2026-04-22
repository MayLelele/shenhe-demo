# -*- coding: utf-8 -*-
"""审核 Agent：OpenAI 兼容 API + 工具循环 + 反思修订。"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from openai import OpenAI

from .memory import MemoryStore
from .tools import TOOL_SPECS, dispatch_tool


REFLECTION_SYSTEM = """你是审核质检员。请只根据「用户原始诉求、工具返回的事实、助手初稿」做检查：
1) 是否遗漏必须核对的规则要点
2) 结论与工具/规则是否矛盾
3) 若信息不足，是否明确列出待补充字段
输出结构（使用中文）：
【质检结果】通过/需修订
【问题清单】...
【修订稿】（若需修订则给出完整替代答复；若通过则重复初稿即可）"""


class AuditAgent:
    def __init__(
        self,
        *,
        mock: bool = False,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        db_path: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.mock = mock
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.session_id = session_id or uuid.uuid4().hex[:12]
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_db = os.path.join(root, "data", "memory.db")
        self.memory = MemoryStore(db_path or default_db)

        self._client: OpenAI | None = None
        if not mock:
            key = api_key or os.environ.get("OPENAI_API_KEY")
            if not key:
                raise ValueError("未设置 OPENAI_API_KEY，可使用 --mock 运行演示模式")
            kwargs: dict[str, Any] = {"api_key": key}
            if base_url or os.environ.get("OPENAI_BASE_URL"):
                kwargs["base_url"] = base_url or os.environ.get("OPENAI_BASE_URL")
            self._client = OpenAI(**kwargs)

        self.short_term: list[dict[str, Any]] = []

    def _system_prompt(self) -> str:
        mem = self.memory.format_context(self.session_id)
        return f"""你是「提币/KYC 审核辅助」Agent。要求：
- 优先调用工具获取规则与时间，再给出审核建议；不得编造内部规则细节。
- 结论用：倾向通过 / 倾向拒绝 / 信息不足需补充，并简述依据。
- 已知本会话长期记忆摘要：
{mem}
"""

    def run_turn(self, user_message: str) -> str:
        """处理用户一轮输入，返回最终答复（含反思）。"""
        self.memory.append(self.session_id, "user", user_message)
        self.short_term.append({"role": "user", "content": user_message})

        if self.mock:
            return self._run_turn_mock(user_message)

        assert self._client is not None
        draft = self._chat_with_tools(self._client, self.model)
        final = self._reflect(self._client, self.model, user_message, draft)
        self.memory.append(self.session_id, "assistant", final)
        self.short_term.append({"role": "assistant", "content": final})
        return final

    def _chat_with_tools(self, client: OpenAI, model: str) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt()},
            *self.short_term,
        ]
        for _ in range(8):
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_SPECS,
                tool_choice="auto",
                temperature=0.2,
            )
            msg = resp.choices[0].message
            tool_calls = msg.tool_calls
            if not tool_calls:
                text = (msg.content or "").strip()
                return text or "（模型未返回文本）"

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                name = tc.function.name
                out = dispatch_tool(name, tc.function.arguments)
                self.memory.append(
                    self.session_id,
                    "tool",
                    f"{name} -> {out[:2000]}",
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": out,
                    }
                )
        return "（工具调用轮数过多，请简化问题后重试）"

    def _reflect(self, client: OpenAI, model: str, user_message: str, draft: str) -> str:
        messages = [
            {"role": "system", "content": REFLECTION_SYSTEM},
            {
                "role": "user",
                "content": f"【用户】{user_message}\n\n【助手初稿】\n{draft}",
            },
        ]
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
        )
        reflected = (resp.choices[0].message.content or "").strip()
        if "【修订稿】" in reflected:
            parts = reflected.split("【修订稿】", 1)
            revised = parts[-1].strip()
            if revised:
                return f"{reflected}\n\n---\n（已附反思修订；上方为完整质检输出）"
        return f"{draft}\n\n---\n【反思质检】\n{reflected}"

    def _run_turn_mock(self, user_message: str) -> str:
        """无 API 时的演示路径：仍走工具与反思结构（规则简化）。"""
        text = user_message.lower()
        tool_lines: list[str] = []
        if "规则" in user_message or "kyc" in text or "提币" in user_message:
            kw = "kyc2提币"
            for token in ("kyc2", "余额不足", "仅提现审", "提币拒绝", "黑名单"):
                if token in user_message:
                    kw = token
            out = dispatch_tool("lookup_policy_rule", json.dumps({"keyword": kw}))
            self.memory.append(
                self.session_id, "tool", f"lookup_policy_rule -> {out[:2000]}"
            )
            tool_lines.append(f"[lookup_policy_rule] {out}")
        out_time = dispatch_tool("get_audit_utc_time", "{}")
        self.memory.append(
            self.session_id, "tool", f"get_audit_utc_time -> {out_time[:2000]}"
        )
        tool_lines.append(f"[get_audit_utc_time] {out_time}")
        if any(x in user_message for x in ("备注", "金额", "充值", "提币")):
            snap = dispatch_tool("validate_case_snapshot", json.dumps({"case_text": user_message}))
            self.memory.append(
                self.session_id, "tool", f"validate_case_snapshot -> {snap[:2000]}"
            )
            tool_lines.append(f"[validate_case_snapshot] {snap}")

        draft = (
            "【倾向结论】信息不足需补充\n"
            "【依据摘要】"
            + ("已参考工具返回的规则与时间。" if tool_lines else "未触发具体规则匹配；")
            + "\n【建议核对】用户备注、提币金额、充值金额、KYC 状态。"
        )
        reflection = (
            "【质检结果】需修订\n"
            "【问题清单】mock 模式未调用大模型，结论为占位；真实环境以模型输出为准。\n"
            "【修订稿】\n"
            + draft
        )
        final = f"{draft}\n\n---\n【工具轨迹】\n" + "\n".join(tool_lines) + f"\n\n---\n【反思质检】\n{reflection}"
        self.memory.append(self.session_id, "assistant", final)
        self.short_term.append({"role": "assistant", "content": final})
        return final

    def collect_evidence_chain(self) -> list[dict[str, Any]]:
        """自 memory 中按时间顺序取本会话用户输入、工具与助手输出，供外部分页展示。"""
        rows = self.memory.recent(self.session_id, limit=200)
        out: list[dict[str, Any]] = []
        for row in rows:
            k = row["kind"]
            c = row["content"]
            if k == "user":
                out.append({"type": "user", "text": c})
            elif k == "tool":
                if " -> " in c:
                    n, o = c.split(" -> ", 1)
                else:
                    n, o = c, ""
                out.append(
                    {
                        "type": "tool",
                        "name": n.strip(),
                        "output": o,
                    }
                )
            elif k == "assistant":
                out.append({"type": "assistant", "text": c})
        return out

    def close(self) -> None:
        self.memory.close()
