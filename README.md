# 审核辅助 Agent（可运行）

面向「提币 / KYC」类审核场景的最小可运行示例，包含：

- **工具调用**：规则检索、UTC 时间、工单字段校验（内置模拟规则库）
- **记忆**：会话内短期上下文 + SQLite 长期记忆（`data/memory.db`）
- **反思**：对初稿做质检并输出修订说明（真实模式调用独立一轮 LLM）

## 环境

- Python 3.9+
- 真实模式需要 `OPENAI_API_KEY`（或兼容 OpenAI 协议的网关与密钥）

## 安装

```bash
cd audit_agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 编辑填入 OPENAI_API_KEY
```

## 运行

**离线演示（无需 API Key）：**

```bash
python main.py --mock
```

**真实模型（需配置 `.env`）：**

```bash
python main.py
```

可选环境变量：`OPENAI_MODEL`、`OPENAI_BASE_URL`。

## 项目结构

- `audit_agent/tools.py`：工具实现与 OpenAI `tools` 定义
- `audit_agent/memory.py`：SQLite 长期记忆
- `audit_agent/agent.py`：工具循环 + 反思逻辑
- `main.py`：命令行交互入口
- `audit_web.py` + `audit_workbench.html`：本机 Web 审核台（见下方）
- `audit_agent-overview.html`：源码/说明总览单页
- `审核员-main审核可视化.html`：单次工单、审核员视角的静态报告示例

**Web 审核台：**

```bash
python audit_web.py
# 浏览器打开 http://127.0.0.1:8765/ （端口占用时可设环境变量 AUDIT_WEB_PORT）
```

**复盘与变更纪要**（时间线、排障、已知限制）：见 [`执行纪要-复盘.md`](./执行纪要-复盘.md)。

**审核知识库**（规则说明、字段标准、如何新增条目、与 `tools.POLICY_RULES` 同步方式）：见 [`knowledge_base/README.md`](./knowledge_base/README.md)。

## 说明

内置规则片段为演示用途，与完整内控制度一致前请以正式文档与系统为准。
