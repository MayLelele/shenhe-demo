---
name: 审核-skill
description: 要求更新审核知识库时，使用此技能。
---

# 审核-skill

## 指令
1. 检查审核结果是否准确。
2. 若准确：将**可复用的规则与事实**按模板写入 `knowledge_base/entries/`，并更新 `knowledge_base/01-提币KYC-规则条目.md`；需要被 Agent 检索时同步 `audit_agent/tools.py` 的 `POLICY_RULES`（见 `knowledge_base/00-索引与扩展指南.md`）。
3. 若不准：在人工校准后，将**修正后的规则或字段说明**按同样路径写入 `knowledge_base/`，并注明个案与通例的边界。

**知识库入口**：[knowledge_base/README.md](./knowledge_base/README.md)