# Student Quickstart

这份手册给学生使用，目标是从零跑通项目，并产出可以写进简历和结课提交的截图材料。

## 1. 你最终要完成什么

完成后你应该能展示：

- 本地 DeerFlow Paper RAG UI 可以打开。
- Status 显示 LLM、embedding、SQLite、Qdrant 基本可用。
- 至少 ingest 1 篇论文。
- 至少问 3 个论文相关问题，并看到 citations。
- 至少问 1 个无关问题，并看到 no-evidence / insufficient evidence。
- 至少生成 1 个 Wiki entry。
- 至少提交 1 次 helpful/not-helpful feedback。
- 能用 3 分钟讲清楚项目架构和 RAG 主链路。

## 2. 环境准备

推荐环境：

| 项目 | 推荐 |
|---|---|
| 操作系统 | macOS / Linux |
| Python | 3.12 |
| Node.js | 20+ |
| 包管理 | `uv`, Corepack/pnpm |
| LLM provider | OpenAI-compatible API，例如 DeepSeek/OpenAI/Qwen |

确认版本：

```bash
python3 --version
node --version
corepack --version
```

## 3. 克隆项目

```bash
git clone https://github.com/TongTong0828/paper-rag-agent.git
cd paper-rag-agent
```

## 4. 安装后端依赖

```bash
python3 -m pip install -U uv
uv python install 3.12

cd integrations/deer-flow/backend
uv sync --python 3.12
cd ../../..

export PY="$PWD/integrations/deer-flow/backend/.venv/bin/python"
$PY -m pip install -U pip
$PY -m pip install -e ".[dev,embed,ingest]"
```

如果下载 embedding 模型较慢，第一次运行会等待较久，这是正常现象。

## 5. 安装前端依赖

```bash
cd integrations/deer-flow/frontend
corepack enable
corepack pnpm install
cd ../../..
```

## 6. 配置 `.env`

```bash
cp .env.example .env
```

编辑 `.env`，填入自己的 provider：

```bash
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-your-key-here
CHAT_MODEL=deepseek-chat
SMALL_MODEL=deepseek-chat
PAPER_RAG_CONFIG=config/local.yaml
```

注意：

- 不要把真实 API key 发给别人。
- 不要把 `.env` 提交到 git。
- 如果换 OpenAI、Qwen 或其他兼容服务，只要 base URL、key、model 对应正确即可。

## 7. 初始化数据并 ingest 论文

最小演示只需要 1 篇：

```bash
make init-store
make ingest ID=2310.11511
```

推荐课程演示使用 3 篇：

```bash
make ingest ID=2005.11401
make ingest ID=2312.10997
```

完整答辩可以再加：

```bash
make ingest ID=2305.06983
make ingest ID=2104.08663
```

## 8. 启动项目

终端一，启动后端：

```bash
make deerflow-backend
```

终端二，启动前端：

```bash
make deerflow-frontend
```

打开：

```text
http://127.0.0.1:3000/workspace/paper-rag
```

## 9. 按顺序测试 UI

### 9.1 Status

先看 Status 区域。理想状态：

```text
llm-ready; embed-ok; qdrant-ok
```

如果不是，先看 [troubleshooting_faq.md](troubleshooting_faq.md)。

### 9.2 QA

先问：

```text
What is Self-RAG and what are reflection tokens?
```

你应该看到：

- 有自然语言答案。
- 有 citations。
- citation 指向 indexed paper/chunk。
- 没有报 503。

再问：

```text
How does Self-RAG decide when to retrieve at inference?
```

然后问一个无关问题：

```text
What's the weather in Beijing tomorrow?
```

你应该看到系统拒答或提示证据不足，而不是编天气。

### 9.3 Papers

检查 Papers 列表中是否能看到刚 ingest 的论文。

### 9.4 Wiki

对 Self-RAG 论文生成 Wiki note。截图时要展示标题、摘要或知识点。

### 9.5 Feedback

对一个答案点击 helpful 或 not-helpful。这个动作代表真实产品里的 feedback loop。

## 10. 运行验证命令

```bash
make deerflow-smoke
make eval-golden
```

如果你配置了真实 LLM provider：

```bash
make eval-golden-qa
```

课程提交时，至少截图 `make eval-golden` 成功结果。

## 11. 结课需要提交什么

建议提交一个 zip 或仓库链接，包含：

| 材料 | 要求 |
|---|---|
| UI 截图 | Status、QA、citations、Papers、Wiki、Feedback |
| 命令截图 | `make eval-golden` 或 smoke test |
| 简历 bullet | 3-5 条，参考 `paper_rag_agent_project_manual.md` |
| 架构图 | 手画或截图，说明 browser -> gateway -> paper_rag -> SQLite/Qdrant/LLM |
| 3 分钟讲解稿 | 说明业务目标、RAG 链路、Agentic 决策、可靠性和评测 |

## 12. 三分钟讲解模板

```text
这个项目是一个集成到 DeerFlow 工作台里的 Agentic RAG 论文问答系统。
用户可以 ingest 论文，然后在 UI 里问答、查看 citations、生成 Wiki、提交 feedback。

技术上，后端用 FastAPI adapter 接入 paper_rag package。paper_rag 负责 PDF parsing、chunk、embedding、SQLite/Qdrant 存储、BM25/FTS5 + dense retrieval、RRF fusion 和 rerank。

它和普通 RAG 不同的是，系统加入了 query rewrite、HyDE、reflective retrieval、abstain 和 citation validation。证据不足时会拒答，生成后会校验引用是否来自 retrieved chunks。

工程上，我可以通过 runtime status 定位依赖问题，通过 smoke test 和 golden set eval 验证项目不是只适配一个 demo。
```

## 13. 学生最容易卡住的地方

| 卡点 | 先做什么 |
|---|---|
| 后端 venv 不存在 | 重新执行 `uv sync --python 3.12` |
| QA 返回 503 | 看 Status，通常是 embedding 或 LLM 未 ready |
| 没有 citations | 确认论文已 ingest，并且 Qdrant 有向量 |
| 前端打不开 | 确认 backend 和 frontend 在两个终端都启动 |
| 模型回答不稳定 | 用 `make eval-golden` 看检索，而不是只看一次回答 |

## 14. 学习顺序

不要一开始就改代码。建议顺序：

1. 跑通 UI。
2. 跑通 ingest。
3. 跑通 QA 和 citations。
4. 跑通 no-evidence。
5. 跑通 eval。
6. 画架构图。
7. 再改一个小优化，例如新增 golden question 或调整 query rewrite。

先让系统可运行，再让自己能讲清楚，最后再做优化。
