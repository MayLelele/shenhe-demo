#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机 Web：表单提交 → AuditAgent，返回 JSON（结论 + 证据链）。"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

if __name__ == "__main__":
    _r = os.path.dirname(os.path.abspath(__file__))
    if _r not in sys.path:
        sys.path.insert(0, _r)

from dotenv import load_dotenv

load_dotenv()


def _infer_verdict(text: str) -> str:
    """从答复文本抽取标签；优先【倾向结论】，其次隐去「则倾向」后在前段匹配。"""
    t = text or ""
    m = re.search(r"【倾向结论】\s*([^\n]+)", t)
    if m:
        line = m.group(1).strip()
        if "信息不足" in line:
            return "信息不足需补充"
        if "拒绝" in line:
            return "倾向拒绝"
        if "通过" in line and "不通过" not in line and "未通过" not in line:
            return "倾向通过"
    before_traj = t.split("【工具轨迹】", 1)[0] if "【工具轨迹】" in t else t
    scrub = re.sub(
        r"则倾向(通过|拒绝)[^。；\n]*", "", before_traj
    )  # 去掉政策原文里的子句
    s = re.sub(
        r"未找到与[「][^」]+[」]直接匹配[^。]+。",
        "",
        scrub,
        count=0,
    )
    s = s[:10000]
    m2 = re.search(r"倾向(通过|拒绝|信息不足)", s)
    if m2 and m2.end() < 2000:
        w = m2.group(1)
        return {
            "通过": "倾向通过",
            "拒绝": "倾向拒绝",
            "信息不足": "信息不足需补充",
        }.get(w, "见下方完整结论")
    if re.search(
        r"信息不足(?!的)|需补充(?!条件)|待补充(?!的)",
        before_traj[:4000],
    ):
        return "信息不足需补充"
    return "见下方完整结论"


def _build_case(
    user_id: str, remark: str, withdraw: str, deposit: str
) -> str:
    return (
        f"用户ID：{user_id.strip()}\n"
        f"用户备注：{remark.strip()}\n"
        f"提币金额：{withdraw.strip()}\n"
        f"充值金额：{deposit.strip()}\n"
    )


def _evidence_extras(
    evidence: list[dict[str, Any]], reply: str
) -> dict[str, Any]:
    """从证据链中抽取 validate 解析结果、规则摘要，便于前端高亮。"""
    extra: dict[str, Any] = {"validate_json": None, "policy_hits": []}
    for e in evidence:
        if e.get("type") != "tool":
            continue
        name = e.get("name", "")
        out = e.get("output", "")
        if name == "validate_case_snapshot" and out.strip().startswith("{"):
            try:
                extra["validate_json"] = json.loads(out)
            except json.JSONDecodeError:
                pass
        if name == "lookup_policy_rule":
            extra["policy_hits"].append(out)
    return extra


def _run_audit(
    case_text: str, *, use_mock: bool, model: str | None
) -> dict[str, Any]:
    from audit_agent.agent import AuditAgent

    kwargs: dict[str, Any] = {"mock": use_mock}
    if model:
        kwargs["model"] = model
    agent = AuditAgent(**kwargs)
    try:
        reply = agent.run_turn(case_text)
        ev = agent.collect_evidence_chain()
        sid = agent.session_id
    finally:
        agent.close()
    verdict = _infer_verdict(reply)
    extras = _evidence_extras(ev, reply)
    return {
        "ok": True,
        "session_id": sid,
        "verdict": verdict,
        "reply": reply,
        "evidence": ev,
        "case_text": case_text,
        "model": model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "mock": use_mock,
        **extras,
    }


def _cors(h: BaseHTTPRequestHandler) -> None:
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")


def _read_body(h: BaseHTTPRequestHandler) -> bytes:
    n = int(h.headers.get("Content-Length", "0") or 0)
    if n <= 0:
        return b""
    return h.rfile.read(n)


def make_handler(www_root: str) -> type[BaseHTTPRequestHandler]:
    class H(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_OPTIONS(self) -> None:  # noqa: N802
            if self.path in ("/api/audit", "/api/health"):
                self.send_response(HTTPStatus.NO_CONTENT)
                _cors(self)
                self.end_headers()
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "not found")

        def do_GET(self) -> None:  # noqa: N802
            p = urllib.parse.urlparse(self.path).path
            if p in ("/", "/audit_workbench.html"):
                fp = os.path.join(www_root, "audit_workbench.html")
                if not os.path.isfile(fp):
                    self.send_error(HTTPStatus.NOT_FOUND, "missing audit_workbench.html")
                    return
                with open(fp, "rb") as f:
                    data = f.read()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                _cors(self)
                self.end_headers()
                self.wfile.write(data)
                return
            if p == "/api/health":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                _cors(self)
                self.end_headers()
                self.wfile.write(
                    b'{"ok":true,"service":"audit_workbench"}\n'
                )
                return
            self.send_error(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self) -> None:  # noqa: N802
            p = urllib.parse.urlparse(self.path).path
            if p != "/api/audit":
                self.send_error(HTTPStatus.NOT_FOUND, "not found")
                return
            raw = _read_body(self)
            try:
                data = (
                    json.loads(raw.decode("utf-8")) if raw else {}
                )  # type: ignore[assignment]
            except json.JSONDecodeError as e:
                _write_json(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "invalid json", "detail": str(e)},
                )
                return
            user_id = str(data.get("user_id") or "").strip()
            remark = str(data.get("remark") or data.get("用户备注") or "").strip()
            withdraw = str(
                data.get("withdraw", data.get("提币金额") or "")
            ).strip()
            deposit = str(
                data.get("deposit", data.get("充值金额") or "")
            ).strip()
            if not (remark and withdraw and deposit):
                _write_json(
                    self,
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {
                        "ok": False,
                        "error": "请填写 用户备注、提币金额、充值金额",
                    },
                )
                return
            case_text = _build_case(
                user_id or "未填",
                remark,
                withdraw,
                deposit,
            )
            use_mock = bool(data.get("mock"))
            if not use_mock and not os.environ.get("OPENAI_API_KEY"):
                _write_json(
                    self,
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "ok": False,
                        "error": "未设置 OPENAI_API_KEY",
                        "hint": '请求中设置 "mock": true 可本地演示，或配置 .env',
                    },
                )
                return
            mod = (data.get("model") or "").strip() or None
            try:
                res = _run_audit(case_text, use_mock=use_mock, model=mod)
            except Exception as e:
                _write_json(
                    self,
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "ok": False,
                        "error": str(e),
                    },
                )
                return
            _write_json(self, HTTPStatus.OK, res)

    return H


def _write_json(h: BaseHTTPRequestHandler, status: int, obj: dict) -> None:
    body = json.dumps(obj, ensure_ascii=False) + "\n"
    b = body.encode("utf-8")
    h.send_response(status)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(b)))
    _cors(h)
    h.end_headers()
    h.wfile.write(b)


def main() -> None:
    www = os.path.dirname(os.path.abspath(__file__))
    host = os.environ.get("AUDIT_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("AUDIT_WEB_PORT", "8765"))
    H = make_handler(www)
    s = ThreadingHTTPServer((host, port), H)
    print(f"审核台: http://{host}:{port}/")
    print("按 Ctrl+C 结束")
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        s.shutdown()
        pass


if __name__ == "__main__":
    main()
