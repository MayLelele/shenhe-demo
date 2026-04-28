---
name: 审核-skill
description: 要求更新审核知识库时，使用此技能。
---

# 审核-skill

## 指令
1. 检查审核结果是否准确。
2. 若准确：在 **Web 审核台** 完成「人工质检」选 **准确** 并提交（可选备注）；若离开 Web，则手动将可复用内容按模板写入 `knowledge_base/entries/` 并更新 `01-`。
3. 若不准：在审核台选 **不准确**，填写**评价**与**审核建议（入知识库）**并提交，会写入 `knowledge_base/entries/feedback/`；再定期把可复用规则合并进 `01-` 与 `audit_agent/tools.py` 的 `POLICY_RULES`（见 `knowledge_base/00-索引与扩展指南.md`）。

**知识库入口**：[knowledge_base/README.md](./knowledge_base/README.md)