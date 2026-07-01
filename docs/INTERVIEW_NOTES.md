# 面试材料速查（基于 paper_rag 真实数据）

> 项目讲完之后被追问什么、用什么数据反击。

## 一句话定位

> "我做了一个面向 Agent 的论文研究 RAG Workbench：能自动发现候选论文、构建本地知识库、用 DeerFlow tool/subagent 调用 Agentic RAG，并用 strict golden、real/stress 和 claim-level 三层评测验证检索、引用、拒答、语义覆盖和 LLM-assisted recall。"

## 数字（拍着指标说）

| 维度 | 数字 |
|---|---|
| 代码 | 70+ 个 Python 模块、7 个 Harness 工具入口 |
| 文档 | 12 份 ADR、5 份顶层文档（PLAN/STATUS/ARCHITECTURE/OPERATIONS/ACCEPTANCE_REPORT） |
| 测试 | pytest focused tests + import smoke + secret scan + golden gate |
| 评测集 | strict golden 60 条，其中 45 条正例带 chunk-level 标注、15 条 no-evidence；real/stress 40 条；claim-level 40 条，其中 30 条正例带 90 个 expected claims、10 条 no-evidence |
| 检索 gate | `positive_paper_recall@10=0.989`, `positive_chunk_recall@10=0.811`, `positive_paper_mrr=0.989`, `fpr@10=0.000`, errors=0 |
| QA gate | `cite_existence=1.000`, `cite_precision=0.867`, `cite_paper_precision=0.922`, `must_contain=0.933`, `no_answer_success=1.000` |
| Claim gate | `claim_recall=0.811`, `grounded_claim_recall=0.722`, `no_answer_success=1.000`, violations=0 |
| LLM recall | baseline chunk recall@10=0.717；local rewrite+HyDE=0.817；LLM rewrite+HyDE=0.933，gain=10，harm_rate=0.050 |
| 验收链路 | topic discovery → arxiv/Semantic Scholar 候选排序 → 手动 ingest → pymupdf 解析 → 切片 → bge-m3 encode → Qdrant + SQLite 双库 → hybrid (dense+FTS5) + RRF → reranker → qa_agentic (intent+rewrite+reflect) → citation 校验 |

## 高频追问 + 准备好的硬回答

**Q: 你的 RAG 跟普通的 langchain RAG 有什么区别？**
> 四个独有点。一是 **Paper Discovery Loop**：topic → arXiv/Semantic Scholar 候选 → dedup → ranking reason → 手动 ingest，把“找论文”也做成可解释闭环。二是 **paper_qa 内闭环**：意图分类 → query rewrite + HyDE → dense+FTS5 hybrid + RRF → reranker → 反思迭代，主 agent 只看到一次 tool 调用，硬上限 max_inner_iters=3 防死循环。三是 **citation 双保险**：prompt 强制 [chunk:xxx] + 后置正则检测 [1] / (Author 2020) 形态。四是 **自进化 Wiki**：从论文沉淀概念条目，patch-only + self_eval gate + 异步队列。

**Q: 怎么验证 RAG 真的工作？怎么避免幻觉？**
> 我把评测拆成三层。第一层是 retrieval-only，不调用大模型，只用 golden set 的 `relevant_paper_ids/relevant_chunk_ids` 和检索 top-k 做 ID 对比，所以可以稳定检查 paper recall、chunk recall、MRR、nDCG 和 FPR。第二层是 citation audit，调用模型生成答案，但不用 LLM judge，检查 citation existence、citation precision/recall、must-contain 和 no-answer success，并把 `relevant_chunk_ids` 和 `citation_chunk_ids` 分开。第三层是 claim-level eval，把答案拆成 expected claims，检查 claim_recall 和 grounded_claim_recall，确认答案不只是引用真实 chunk，也覆盖关键语义结论。三道防线：(1) 生成前 evidence selection 只给 LLM 精简证据；(2) prompt 强制使用 `[chunk:<id>]`；(3) `validate_citations` 剔除不在 selected evidence 的引用，no-evidence 走 abstain。

**Q: 为什么 retrieval-only 不需要 API key？**
> 因为它测的是检索系统，不测语言生成。流程是：问题 → 本地 rewrite heuristic → dense/sparse/hybrid/rerank → top-k chunk ids，然后和 golden label 的 paper/chunk ids 做精确匹配。它像搜索引擎离线评测，不需要 LLM 主观打分。`eval-golden-qa` 和可选 judge 才需要 API。

**Q: FPR 是怎么定义的？为什么不是 top10 里非目标都算错？**
> RAG 检索会召回相邻论文，不能把“正确证据后面的相关背景论文”都算成错。项目里的 FPR 只统计明确标注的危险误召回，并且只看它是否出现在第一个正确 evidence 之前。这样更贴近真实风险：模型最容易被前排错误证据带偏。

**Q: 为什么用双库（Qdrant + SQLite）？**
> 职责分离（ADR-0004）。Qdrant 只做向量召回 + payload metadata 过滤；SQLite 做关系数据 + 状态机 + ingest_runs 流水 + wiki_entries + qa_cache + FTS5 全文索引。**FTS5 是 SQLite 自带的**，零依赖换 BM25 + 增量更新（ADR-0010）。

**Q: 怎么做混合检索？**
> Dense (bge-m3) top 20 + Sparse (FTS5 / rank_bm25) top 20 → RRF (k=60) 融合 → 取 top_k*2 给 reranker (BGE-reranker-v2-m3) → 截 top_k。配置 `retrieve.sparse_backend=fts5|rank_bm25` 可切，FTS5 异常自动 fallback。BM25 search 接受 paper_ids 入参，先打分后过滤，避免 top-N 全是无关 paper 导致 0 命中（P1 #9）。

**Q: 怎么证明混合检索、rerank、rewrite 不是堆概念？**
> 我做了 retrieval ablation。dense-only 的 positive chunk recall@10 是 0.767，sparse-only 很快但 chunk recall 只有 0.567；hybrid RRF 把 chunk recall 拉到 0.811；hybrid+rerank+local rewrite 同时保持 paper recall@10=0.989、MRR=0.989、chunk recall@10=0.811。这个实验说明 sparse 负责术语精确匹配，dense 负责语义召回，RRF/rerank/rewrite 负责排序和关键概念展开。

**Q: LLM-assisted retrieval 怎么证明有用，不是又让模型当裁判？**
> 我把 LLM rewrite/HyDE 单独做成 recall eval，不让模型判断答案好坏。三种策略共用同一个 claim set 的 paper/chunk label：baseline_no_rewrite 的 chunk recall@10 是 0.717，local_rewrite_hyde 是 0.817，llm_rewrite_hyde 是 0.933。这里的 gain/harm 都按 ID 命中计算，LLM 只参与改写查询，不参与评分。这样能回答“LLM 加在召回阶段有没有实际收益”，同时避免 LLM judge 的不稳定。

**Q: 真实环境集成时遇到什么坑？**
> 4 个回归（ADR-0012）。(1) `arxiv` 包升 v4 删了 `Result.download_pdf`，改用 `client.download_pdf(result, ...)` + httpx 兜底。(2) `qdrant-client` 1.18 弃用 `client.search()`，改用 `query_points()` + 兼容写法。(3) `wiki/store.py` 残留 SyntaxError 被 sqlmodel 缺失掩盖。(4) `init_store.py` 直接 new client 绕过 `get_client` 兜底，加了 `qdrant.local_path` 配置后才发现。所有问题都通过 try/except + 兜底降级吸收，主路径无 `database is locked` / `qdrant unreachable` 异常。

**Q: 怎么跟 DeerFlow 集成的？**
> 不入侵 harness/app boundary。三处接入：`backend/.../community/paper_rag/tools.py` 用 LangChain `@tool` 包装 7 个工具（paper_qa/search/section/compare/discover/wiki_lookup/export_bibtex）；`backend/.../subagents/builtins/paper_research.py` 注册 `paper-research` 专家 subagent；`config.example.yaml` 把 paper 工具挂到 `paper` tool group。`paper_discover` 只返回候选和理由，不把候选当最终证据；最终回答仍回到 indexed chunks。

**Q: 怎么防 Wiki 越改越烂？**
> 五条护栏（ADR-0007）。(1) 频率限制：单 entry 24h 内最多 1 次更新，`lock_until` 字段控制。(2) Patch-only：LLM 只能输出 `add_*` 字段，definition 仅在显式给出新值时覆盖，禁止整条重写。(3) self_eval gate：LLM 同时输出置信度，<0.7 直接丢弃。(4) 版本日志：`wiki_versions` 表每次 upsert 写一条。(5) 默认关闭：`wiki.enabled=false`，先把 RAG 主路径打稳。(6) 一致性 heuristic：`consistency.py` 标 short_def / no_key_papers / self_related。

## 不要落入的陷阱

- 不要说“只跑了 demo question”——现在有 60 条 strict golden、40 条 real/stress 和 40 条 claim-level eval。
- 不要把 retrieval-only 讲成“模型评测”——它是 ID-level 离线检索评测，不需要 API。
- 不要把 memory/discovery/wiki 说成最终证据来源——最终答案仍然只认 indexed chunks 和 citations。
- 不要夸成生产 SaaS——正确定位是本地课程/面试级 Agent Workbench，部署、权限、监控可以作为后续扩展。

## 一图甩出去（如果对方问架构）

```
topic ─► Paper Discovery Loop ─► candidates + reasons ─► manual ingest
                                                        │
arxiv/s2/local ◄────────────────────────────────────────┘
          └─► MinerU/pymupdf ─► section+chunk+modality ─► Qdrant + SQLite
                                                                      │
DeerFlow Lead Agent ─► paper-research subagent ─► 7 paper tools ─► paper_qa ──┤
                                                              ↓       │
                                       intent → rewrite → hybrid ────┤
                                                  (dense+FTS5 RRF)    │
                                                  → rerank → reflect  │
                                                  → cite check        │
                                                                      │
              wiki_lookup  ◄────  自进化 Wiki ◄─ async queue ◄────────┘
```
