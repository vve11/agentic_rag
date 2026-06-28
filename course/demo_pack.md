# Course Demo Pack

这份文档用于课程销售页、直播演示和学生结课答辩。它固定了推荐论文、演示问题、演示顺序和验收标准，避免每次演示都临场找问题。

## 1. 固定 Demo 数据

推荐先 ingest 下面 5 篇论文。它们覆盖经典 RAG、Agentic RAG、主动检索、RAG survey、检索评测与幻觉问题，足够支撑简历和面试讲解。

| 顺序 | arXiv ID | 主题 | 演示价值 |
|---:|---|---|---|
| 1 | `2310.11511` | Self-RAG | Agentic RAG、reflection token、按需检索 |
| 2 | `2005.11401` | Original RAG | 经典 RAG、parametric/non-parametric memory |
| 3 | `2312.10997` | RAG Survey | Naive/Advanced/Modular RAG、HyDE、rerank、chunk |
| 4 | `2305.06983` | FLARE | active retrieval、低置信度触发检索 |
| 5 | `2104.08663` | BEIR | BM25 baseline、zero-shot retrieval、检索评测 |

可选增强论文：

| arXiv ID | 主题 | 适合补充的问题 |
|---|---|---|
| `2401.01313` | LLM hallucination survey | 幻觉类型、fact checking、retrieval mitigation |

建议课堂最小数据集只要求前 3 篇，完整答辩要求至少 5 篇。

## 2. 一键准备顺序

从仓库根目录运行：

```bash
export PY="$PWD/integrations/deer-flow/backend/.venv/bin/python"

make init-store
make ingest ID=2310.11511
make ingest ID=2005.11401
make ingest ID=2312.10997
make ingest ID=2305.06983
make ingest ID=2104.08663
```

如果 arXiv 网络不稳定，可以先只 ingest `2310.11511` 和 `2005.11401`，保证最小演示可用。

## 3. 标准演示问题

机器可读版本在：

```text
course/demo_questions.jsonl
```

课堂推荐按下面顺序演示。

| 编号 | 问题 | 预期表现 | 讲解点 |
|---|---|---|---|
| 1 | What is Self-RAG and what are reflection tokens? | 返回 Self-RAG 定义和 citations | 基础论文 QA |
| 2 | How does Self-RAG decide when to retrieve at inference? | 解释 Retrieve token / on-demand retrieval | Agentic 检索决策 |
| 3 | What are the three critique tokens in Self-RAG and what do they evaluate? | 提到 relevance/support/usefulness | 反思式证据评价 |
| 4 | What is the original RAG paper's main contribution? | 解释 parametric + non-parametric memory | 经典 RAG baseline |
| 5 | What is the difference between RAG-Sequence and RAG-Token? | 比较 sequence/token 粒度 | RAG 模型结构 |
| 6 | What are Naive RAG, Advanced RAG, and Modular RAG? | 总结三类 RAG | RAG taxonomy |
| 7 | What is HyDE (Hypothetical Document Embeddings)? | 解释假设文档 embedding | query rewrite / pre-retrieval |
| 8 | What is reranking in RAG and why use it? | 解释 post-retrieval rerank | recall/precision tradeoff |
| 9 | Compare Self-RAG and FLARE: when does each retrieve? | 跨论文比较 retrieve 时机 | 多论文综合 |
| 10 | What's the weather in Beijing tomorrow? | 触发 no-evidence / insufficient evidence | 拒答和幻觉控制 |

## 4. 十分钟课堂演示脚本

1. 打开 `README.md`，说明这是一个 DeerFlow 集成的 Agentic RAG 论文工作台。
2. 打开 `/workspace/paper-rag`，先展示 Status，确认 LLM、embedding、SQLite、Qdrant 状态。
3. 展示 Knowledge Builder，说明一篇论文会经过 fetch、parse、chunk、embed、index、wiki 等构建阶段。
4. 问问题 1，展示 answer + citations。
5. 展开 Loop Trace，讲 intent、retrieval round、reflect、abstain 和 stopped_by。
6. 展示 Research Memory，强调它只用于延续研究上下文，不作为最终证据。
7. 点击 citations，讲“引用不是模型自由生成的 `[1]`，而是 chunk 级证据”。
8. 问问题 7 或 8，讲 HyDE/rerank 等 RAG 优化点。
9. 问问题 9，讲跨论文比较需要召回多个 paper 的证据。
10. 问问题 10，展示 no-evidence 拒答。
11. 生成一篇 Wiki note，说明系统不是只有 chat，还有知识沉淀。
12. 点击 helpful/not-helpful，说明 feedback 如何进入 hard cases 和 golden set。

## 5. 学生答辩验收标准

学生不需要每个模块都改过，但至少要能完成下面演示：

| 项目 | 通过标准 |
|---|---|
| 启动 | backend/frontend 均能启动，UI 可访问 |
| 数据 | 至少 1 篇论文成功 ingest，推荐 3 篇以上 |
| QA | 至少 3 个相关问题返回答案和 citations |
| 拒答 | 至少 1 个无关问题触发 no-evidence 或 insufficient evidence |
| 产品闭环 | 展示 Knowledge Builder、Wiki、Feedback 中至少 2 个非 QA 页面 |
| 评测 | 能运行 `make eval-golden` 或解释 golden set 的作用 |
| 表达 | 能讲清 dense/sparse/RRF/rerank/loop trace/research memory/abstain/citation validation |

## 6. 演示失败时的处理

| 现象 | 现场处理 |
|---|---|
| LLM 不可用 | 用 retrieval-only 问题演示 citations，并说明 status 暴露了依赖问题 |
| embedding 缺失 | 运行 `$PY -m pip install -e ".[embed,ingest]"` 后重试 |
| arXiv 下载失败 | 换成本地 PDF ingest，或只使用已有 indexed papers |
| Qdrant 无向量 | 运行 `make deerflow-rebuild-index` |
| 答案不稳定 | 讲 golden set：优化 RAG 不能只看一次回答 |

## 7. 讲给面试官的一句话

```text
我用这套固定 demo 不是为了背答案，而是为了覆盖 RAG 项目最容易被追问的能力：能不能检索到证据，能不能带引用回答，证据不足时会不会拒答，改动后能不能用 golden set 回归验证。
```

升级版表达：

```text
这个 demo 还能展示普通 RAG 项目很少做的三件事：Loop Trace 让 Agentic 决策可见，Research Memory 让多轮研究任务可延续但不污染证据链，Knowledge Builder 让论文从 ingest 到 index 的状态可解释。
```
