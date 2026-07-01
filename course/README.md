# Course Materials

这个目录放课程交付材料，面向“学生能跑通、能演示、能写进简历、能经得住面试追问”的使用场景。

## 推荐阅读顺序

| 顺序 | 文件 | 用途 |
|---:|---|---|
| 1 | [student_quickstart.md](student_quickstart.md) | 学生从 clone 到跑通 UI 的操作手册 |
| 2 | [demo_pack.md](demo_pack.md) | 固定 demo 论文、标准问题和课堂演示脚本 |
| 3 | [troubleshooting_faq.md](troubleshooting_faq.md) | 常见报错、现场演示事故和排查方式 |
| 4 | [paper_rag_agent_project_manual.md](paper_rag_agent_project_manual.md) | 完整技术手册，适合课程讲义和面试复习 |
| 5 | [../docs/RAG_EVAL_GUIDE.md](../docs/RAG_EVAL_GUIDE.md) | 三层 RAG Eval、全部评测集、命令、指标和报告说明 |
| 6 | [demo_questions.jsonl](demo_questions.jsonl) | 机器可读的标准演示问题集 |

PDF 版技术手册在：

```text
course/paper_rag_agent_project_manual.pdf
```

重新生成 PDF：

```bash
make course-pdf PY=/path/to/python-with-reportlab
```

## 课程交付最小闭环

学生至少应该完成：

1. 按 `student_quickstart.md` 跑通本地 DeerFlow UI。
2. 按 `demo_pack.md` ingest 至少 1-3 篇论文。
3. 用 Discovery Loop 找候选论文，再完成 ingest、QA、citations、Loop Trace、Research Memory、no-evidence、Wiki、Feedback 演示。
4. 跑通 `make eval-golden` 和 `make eval-claims`，并能解释 retrieval、citation、claim 三层评测。
5. 参考技术手册写出 3-5 条简历 bullet。
6. 能用 3 分钟讲清系统架构、Paper Discovery Loop、DeerFlow Harness 接入、RAG 主链路、Agentic 决策、记忆压缩边界和可靠性设计。

## 讲师建议

- 第一节课只要求跑通，不要求理解所有源码。
- 第二节课讲 Paper Discovery Loop、Knowledge Builder、ingest、chunk、embedding、SQLite/Qdrant。
- 第三节课讲 DeerFlow Harness、paper_rag tool adapter、paper-research subagent、paper_discover、dense/sparse、RRF、rerank、query rewrite、HyDE 和 Loop Trace。
- 第四节课讲 research memory compression、abstain、citation validation、feedback、golden/claim set 和 LLM-assisted recall。
- 最后一节课做答辩：UI 演示 + 架构图 + 简历 bullet + 面试追问。

课程目标不是让学生背答案，而是让学生能解释：为什么这样设计、替代方案是什么、这个设计解决了什么失败模式。
