# -*- coding: utf-8 -*-
"""可被 Agent 调用的工具（内置规则库模拟真实工单/知识库查询）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

# 与《审核流程梳理》常见分支对齐的简化规则片段，仅供辅助决策演示。
POLICY_RULES: dict[str, str] = {
    "kyc2提币": (
        "若用户备注含「kyc2提币审」或「kyc2提现审」：需确认 KYC2 已完成；"
        "若提币金额大于充值金额则倾向拒绝；若提币金额不大于充值金额则倾向通过。"
    ),
    "提币拒绝": "若备注含「提币拒绝」：倾向直接拒绝（需核对系统记录与原因码）。",
    "余额不足": (
        "若备注严格为「余额不足」：将提币金额与「允许余额」比较；大于则拒绝，否则通过。"
    ),
    "仅提现审": (
        "若备注严格为「仅提现审」：将提币金额与充值金额比较；大于则拒绝，否则通过。"
    ),
    "零充值黑名单": (
        "零充值且无合约活动时，若综合因素为黑名单：需结合设备指纹/客服哈希/同IP用户数"
        "与合约历史盈利等条件按流程表分支判断（详见内部完整流程文档）。"
    ),
}


def lookup_policy_rule(keyword: str) -> str:
    """按关键词检索内部规则摘要（模拟知识库/规则引擎）。"""
    k = (keyword or "").strip()
    if not k:
        return "请提供关键词，例如：kyc2提币、余额不足、仅提现审、提币拒绝、零充值黑名单。"
    hits = []
    for name, body in POLICY_RULES.items():
        if k.lower() in name.lower() or name.lower() in k.lower():
            hits.append(f"【{name}】{body}")
    if not hits:
        return (
            f"未找到与「{k}」直接匹配的规则条目。可用关键词示例："
            + "、".join(POLICY_RULES.keys())
        )
    return "\n".join(hits)


def get_audit_utc_time() -> str:
    """返回当前 UTC 时间 ISO 字符串（用于工单时间戳一致性）。"""
    return datetime.now(timezone.utc).isoformat()


def normalize_case_json(case_text: str) -> dict[str, Any]:
    """将用户粘贴的半结构化描述尝试解析为字段（演示用轻量解析）。"""
    raw = (case_text or "").strip()
    if not raw:
        return {"error": "case_text 为空"}
    # 简单键值提取：行内「键:值」或「键：值」
    fields: dict[str, Any] = {}
    for line in raw.replace("；", "\n").splitlines():
        line = line.strip()
        if not line:
            continue
        for sep in (":", "："):
            if sep in line:
                key, _, rest = line.partition(sep)
                key, rest = key.strip(), rest.strip()
                if key and rest:
                    fields[key] = rest
                break
    if not fields:
        fields["raw"] = raw
    return fields


def validate_case_snapshot(case_text: str) -> str:
    """
    校验工单字段是否齐全（演示规则）。
    返回 JSON 字符串，供模型引用。
    """
    data = normalize_case_json(case_text)
    required = ["用户备注", "提币金额", "充值金额"]
    missing = [r for r in required if r not in data]
    payload = {
        "parsed_fields": data,
        "missing_required": missing,
        "ready_for_branch": len(missing) == 0,
    }
    return json.dumps(payload, ensure_ascii=False)


TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_policy_rule",
            "description": "根据关键词检索提币/KYC 相关审核规则摘要（内部知识库）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "规则关键词或用户备注中的关键片段",
                    }
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_audit_utc_time",
            "description": "获取当前 UTC 时间 ISO 字符串，用于工单记录时间戳。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_case_snapshot",
            "description": "解析并校验用户提供的工单字段是否齐全（备注、提币金额、充值金额等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "case_text": {
                        "type": "string",
                        "description": "用户粘贴的工单文本，可含多行「键:值」",
                    }
                },
                "required": ["case_text"],
            },
        },
    },
]


def dispatch_tool(name: str, arguments: str | dict[str, Any]) -> str:
    """执行工具并返回字符串结果。"""
    args: dict[str, Any]
    if isinstance(arguments, str):
        args = json.loads(arguments) if arguments.strip() else {}
    else:
        args = arguments

    if name == "lookup_policy_rule":
        return lookup_policy_rule(str(args.get("keyword", "")))
    if name == "get_audit_utc_time":
        return get_audit_utc_time()
    if name == "validate_case_snapshot":
        return validate_case_snapshot(str(args.get("case_text", "")))
    return f"未知工具: {name}"
