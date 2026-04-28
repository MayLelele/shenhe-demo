# 审核台质检反馈（自动生成）

本目录由 `audit_web.py` 在提交「人工质检」时写入，**可提交 Git** 供团队汇总；若含敏感个案，请在 `.gitignore` 中排除 `feedback_log.jsonl` / `人工校准摘要.md`。

| 文件 | 说明 |
|------|------|
| `feedback_log.jsonl` | 每行一条 JSON：含 session、工单字段、系统判定、`qc_result` pass/fail、评价与建议等。 |
| `人工校准摘要.md` | 仅在 **系统审核不准确** 时追加可读片段，便于合并进 `01-提币KYC-规则条目.md` 与 `tools.POLICY_RULES`。 |
