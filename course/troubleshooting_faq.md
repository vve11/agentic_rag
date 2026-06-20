# Troubleshooting FAQ

这份 FAQ 给课程助教和学生使用。排查原则：先看 Status，再看日志，最后才改代码。

## 1. 快速定位顺序

遇到问题时按这个顺序检查：

1. 当前目录是否是仓库根目录。
2. `.env` 是否存在，并且没有写错变量名。
3. `integrations/deer-flow/backend/.venv/bin/python` 是否存在。
4. 后端是否运行在 `http://127.0.0.1:8001`。
5. 前端是否运行在 `http://127.0.0.1:3000`。
6. `/api/paper_rag/status` 是否显示 LLM、embedding、SQLite、Qdrant ready。
7. 至少是否 ingest 过 1 篇论文。
8. Qdrant 是否有向量。

## 2. 环境和安装

### 2.1 `uv: command not found`

原因：没有安装 `uv`。

处理：

```bash
python3 -m pip install -U uv
```

### 2.2 `integrations/deer-flow/backend/.venv/bin/python: no such file`

原因：DeerFlow backend venv 没创建。

处理：

```bash
cd integrations/deer-flow/backend
uv sync --python 3.12
cd ../../..
export PY="$PWD/integrations/deer-flow/backend/.venv/bin/python"
```

### 2.3 Python 版本不对

现象：依赖安装失败，或 DeerFlow backend 报 Python version 不满足。

处理：

```bash
uv python install 3.12
cd integrations/deer-flow/backend
uv sync --python 3.12
```

### 2.4 `pnpm: command not found`

原因：Corepack 未启用。

处理：

```bash
corepack enable
cd integrations/deer-flow/frontend
corepack pnpm install
```

## 3. `.env` 和 LLM

### 3.1 QA 返回 LLM unavailable

常见原因：

- `.env` 不存在。
- `OPENAI_API_KEY` 没填。
- `OPENAI_BASE_URL` 不对。
- `CHAT_MODEL` 不存在或 provider 不支持。

处理：

```bash
cp .env.example .env
```

检查 `.env`：

```bash
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-your-key-here
CHAT_MODEL=deepseek-chat
SMALL_MODEL=deepseek-chat
PAPER_RAG_CONFIG=config/local.yaml
```

注意：不要把真实 key 写进 README、手册、截图或 git commit。

### 3.2 DeepSeek 可以用吗？

可以，只要使用 OpenAI-compatible 配置：

```bash
OPENAI_BASE_URL=https://api.deepseek.com
CHAT_MODEL=deepseek-chat
SMALL_MODEL=deepseek-chat
```

### 3.3 Secret scan 失败

原因：仓库文件里出现了疑似 API key。

处理：

- 把真实 key 移到 `.env`。
- 删除 README、文档、测试输出里的 key。
- 重新运行：

```bash
make secret-scan
```

## 4. Embedding 和 Qdrant

### 4.1 Status 显示 `embed-missing`

原因：`FlagEmbedding` 没装到 DeerFlow backend venv。

处理：

```bash
export PY="$PWD/integrations/deer-flow/backend/.venv/bin/python"
$PY -m pip install -e ".[embed,ingest]"
```

### 4.2 第一次 QA 或 ingest 很慢

原因：BGE embedding / reranker 模型第一次下载。

处理：

- 等待下载完成。
- 保持网络稳定。
- 第二次运行会使用本地缓存。

### 4.3 Status 显示 Qdrant 不可用

本项目默认用 embedded Qdrant，数据目录在：

```text
data/index/qdrant_embedded
```

处理：

```bash
make init-store
make deerflow-rebuild-index
```

### 4.4 QA 没有 citations

常见原因：

- 没有 ingest 论文。
- 论文解析成功但 index 没重建。
- 问题和已入库论文无关。

处理：

```bash
make ingest ID=2310.11511
make deerflow-rebuild-index
```

然后问：

```text
What is Self-RAG?
```

## 5. Ingest

### 5.1 arXiv 下载失败

原因：网络、arXiv 临时不可用、代理问题。

处理：

- 重试同一个 ID。
- 换成另一个推荐 ID。
- 使用本地 PDF：

```bash
export PY="$PWD/integrations/deer-flow/backend/.venv/bin/python"
$PY scripts/ingest_one.py --pdf /absolute/path/to/paper.pdf --title "My Paper"
```

### 5.2 PDF 解析效果差

原因：双栏论文、公式、表格、图片会影响普通文本解析。

处理：

- 课程阶段可以接受 PyMuPDF fallback。
- 高级优化可以接 MinerU。
- 面试时诚实说明 PDF parsing 是当前局限之一。

## 6. Backend / Frontend

### 6.1 Backend 端口被占用

现象：启动后端时报 address already in use。

处理：

```bash
lsof -i :8001
```

结束旧进程后重新运行：

```bash
make deerflow-backend
```

### 6.2 Frontend 打不开

检查：

- `make deerflow-frontend` 是否还在运行。
- 浏览器地址是否是 `http://127.0.0.1:3000/workspace/paper-rag`。
- backend 是否已启动。

处理：

```bash
cd integrations/deer-flow/frontend
corepack pnpm install
cd ../../..
make deerflow-frontend
```

### 6.3 前端能打开，但 QA 请求失败

先确认后端：

```bash
curl http://127.0.0.1:8001/api/paper_rag/status
```

如果 status 不通，说明 backend 没起来或端口不对。

## 7. Eval

### 7.1 `make eval-golden` 失败

常见原因：

- 推荐论文没有 ingest。
- Qdrant index 为空。
- 使用了不同数据集。

处理：

```bash
make ingest ID=2310.11511
make ingest ID=2005.11401
make ingest ID=2312.10997
make deerflow-rebuild-index
make eval-golden
```

### 7.2 `make eval-golden-qa` 失败

原因通常是 LLM provider 不可用，而不是 retrieval 失败。

处理：

- 先跑 `make eval-golden`。
- 确认 `.env`。
- 确认 provider 余额和 model name。

### 7.3 为什么 eval 和 UI 回答不完全一样？

原因：

- LLM generation 有随机性。
- UI 问题可能和 golden question 不完全一致。
- no-judge eval 更关注 citations、must-contain、abstain 等稳定指标。

课程重点不是背固定答案，而是解释为什么这个系统可以被回归验证。

## 8. Demo 现场问题

### 8.1 演示时 LLM 突然不可用怎么办？

不要慌。可以切成 retrieval-only 演示：

```bash
export PY="$PWD/integrations/deer-flow/backend/.venv/bin/python"
$PY scripts/ask.py "What is Self-RAG?" --no-llm --top-k 8
```

讲解点：RAG 系统可以把 retrieval 和 generation 拆开 debug。

### 8.2 问天气时模型回答了怎么办？

说明 abstain threshold 需要校准。现场处理：

- 换成更明显的 out-of-domain 问题，例如 `What is the price of an Nvidia H100 GPU?`
- 运行 golden no-answer case。
- 讲解为什么要有 golden set 和 threshold calibration。

### 8.3 生成答案没有想象中漂亮怎么办？

课程里重点不是文采，而是证据链：

- 是否检索到相关 chunks。
- 是否引用真实 chunks。
- 无证据时是否拒答。
- 是否能通过 eval 定位问题。

## 9. 面试回答模板

问：项目启动失败你怎么排查？

答：

```text
我会先看 runtime status，把问题分成 LLM、embedding、SQLite、Qdrant、frontend routing 几类。然后分别看 `.env`、backend venv、ingest/index 状态和日志。这个项目加 status endpoint 的原因就是让本地课程项目不要卡在黑盒报错里。
```

问：RAG 回答错了你怎么定位？

答：

```text
先看 retrieval trace：原始 query、rewrite variants、dense/sparse 命中、RRF 排名、rerank 结果和最终 citations。如果正确证据没进 top-k，优先调 chunk/rewrite/retrieval；如果证据到了但答案错，才调 prompt、abstain 或 generation。
```

问：为什么要把 FAQ 写进项目？

答：

```text
因为一个能交付的 AI 项目不只是核心算法，还要能让别人稳定运行、复现、排错。FAQ 和 status endpoint 体现的是 developer experience 和课程交付能力。
```
