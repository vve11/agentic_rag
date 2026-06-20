"""End-to-end RAG evaluation runner.

Usage:
    python tests/eval/run_eval.py --file tests/eval/qa_set.example.jsonl
    python tests/eval/run_eval.py --file my.jsonl --no-judge --top-k 8
    python tests/eval/run_eval.py --file my.jsonl --retrieval-only

Outputs:
    - per-item results -> stdout (one line summary)
    - aggregate report -> stdout (table)
    - full json dump   -> data/index/eval_runs/<ts>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from eval.loader import load_jsonl  # noqa: E402
from eval.metrics import (  # noqa: E402
    citation_existence_rate,
    citation_precision,
    false_positive_rate,
    mrr,
    must_contain_score,
    must_not_contain_violations,
    recall_at_k,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True, help="Path to qa_set jsonl")
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--no-judge", action="store_true",
                   help="Skip LLM-judge even when gold_answer is provided")
    p.add_argument("--retrieval-only", action="store_true",
                   help="Only run retrieval (no LLM answering); recall metrics only")
    p.add_argument("--out", default=None, help="Override output JSON path")
    return p.parse_args()


def run() -> int:
    args = parse_args()
    from paper_rag import config as cfg

    cfg.load()
    items = load_jsonl(args.file)
    print(f"loaded {len(items)} items")

    per_item: list[dict] = []
    t0 = time.time()
    for i, it in enumerate(items, 1):
        rec = {
            "qid": it.qid,
            "question": it.question,
            "intent": it.intent,
            "expected_relevant_paper_count": len(it.relevant_paper_ids),
        }
        try:
            if args.retrieval_only:
                from paper_rag.retrieve.pipeline import retrieve_round

                chunks = retrieve_round(it.question, None, args.top_k)
                rec.update(_score_retrieval(chunks, it, args.top_k))
            else:
                from paper_rag.rag.qa_agentic import answer

                out = answer(it.question, paper_ids=None)
                rec["answer"] = out["answer"]
                rec["citations"] = out["citations"]
                trace = out.get("trace", {}) or {}
                rec["stopped_by"] = trace.get("stopped_by")
                abstain = trace.get("abstain") or {}
                rec["abstain_decision"] = abstain.get("decision")
                rec["abstain_evidence_score"] = abstain.get("evidence_score")
                rec["abstain_top_chunk_score"] = abstain.get("top_chunk_score")
                rec["abstain_score_field"] = abstain.get("score_field")
                rec.update(_score_retrieval(out["chunks"], it, args.top_k))
                rec.update(_score_answer(out, it, run_judge=not args.no_judge))
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"

        per_item.append(rec)
        _print_summary(i, len(items), rec)

    elapsed = time.time() - t0
    agg = _aggregate(per_item)
    agg["elapsed_sec"] = round(elapsed, 1)
    agg["n_items"] = len(items)

    print("\n=== AGGREGATE ===")
    for k, v in agg.items():
        print(f"  {k:24s}  {v}")

    out_path = (
        Path(args.out)
        if args.out
        else Path(cfg.load().paths.index_dir) / "eval_runs" / f"{int(time.time())}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"aggregate": agg, "items": per_item}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {out_path}")
    return 0


def _score_retrieval(chunks: list[dict], item, k: int) -> dict:
    pred_papers = [c.get("paper_id") for c in chunks if c.get("paper_id")]
    pred_chunks = [c.get("chunk_id") for c in chunks if c.get("chunk_id")]
    out = {
        "n_retrieved": len(chunks),
        "paper_recall@k": recall_at_k(pred_papers, item.relevant_paper_ids, k),
        "paper_mrr": mrr(pred_papers, item.relevant_paper_ids),
    }
    if item.relevant_chunk_ids:
        out["chunk_recall@k"] = recall_at_k(pred_chunks, item.relevant_chunk_ids, k)
    fpr = false_positive_rate(pred_papers, item.irrelevant_paper_ids, k)
    if fpr is not None:
        out["fpr@k"] = fpr
    return out


def _score_answer(out: dict, item, *, run_judge: bool) -> dict:
    answer_text = out.get("answer", "")
    cites = out.get("citations", [])
    retrieved_ids = [c.get("chunk_id") for c in out.get("chunks", []) if c.get("chunk_id")]
    res = {
        "n_citations": len(cites),
        "cite_existence": citation_existence_rate(cites, retrieved_ids),
        "must_contain": must_contain_score(answer_text, item.must_contain),
        "violations": must_not_contain_violations(answer_text, item.must_not_contain),
    }
    if not item.relevant_paper_ids:
        trace = out.get("trace", {}) or {}
        abstain_decision = (trace.get("abstain") or {}).get("decision")
        stopped_by = trace.get("stopped_by")
        res["no_answer_ok"] = float(
            stopped_by in {"no_evidence_abstain", "no_chunks"}
            or abstain_decision in {"no_evidence", "no_chunks"}
            or (not cites and _looks_like_insufficient_evidence(answer_text))
        )
    cp = citation_precision(cites, item.relevant_chunk_ids)
    if cp is not None:
        res["cite_precision"] = cp

    if run_judge and item.gold_answer:
        from eval.judge import judge

        res["judge"] = judge(item.question, item.gold_answer, out.get("answer", ""))
    return res


def _print_summary(idx: int, total: int, rec: dict) -> None:
    if "error" in rec:
        print(f"[{idx}/{total}] {rec['qid']} ERROR {rec['error'][:120]}")
        return
    bits = [f"recall@k={rec.get('paper_recall@k', 0):.2f}",
            f"mrr={rec.get('paper_mrr', 0):.2f}",
            f"cites={rec.get('n_citations', 0)}",
            f"must={rec.get('must_contain', 1):.2f}"]
    if "cite_precision" in rec:
        bits.append(f"cite_p={rec['cite_precision']:.2f}")
    print(f"[{idx}/{total}] {rec['qid']} | " + " | ".join(bits))


def _aggregate(per_item: list[dict]) -> dict:
    def _avg(key: str) -> float:
        vals = [r[key] for r in per_item if isinstance(r.get(key), (int, float))]
        return round(mean(vals), 3) if vals else 0.0

    def _avg_in(rows: list[dict], key: str) -> float:
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return round(mean(vals), 3) if vals else 0.0

    positives = [r for r in per_item if r.get("paper_recall@k") is not None and _has_relevant_paper(r)]
    no_answer = [r for r in per_item if r.get("paper_recall@k") is not None and not _has_relevant_paper(r)]

    answer_rows = [r for r in per_item if "answer" in r]

    out = {
        "paper_recall@k": _avg("paper_recall@k"),
        "paper_mrr": _avg("paper_mrr"),
        "positive_paper_recall@k": _avg_in(positives, "paper_recall@k"),
        "positive_paper_mrr": _avg_in(positives, "paper_mrr"),
        "chunk_recall@k": _avg("chunk_recall@k"),
        "fpr@k": _avg("fpr@k"),
        "errors": sum(1 for r in per_item if r.get("error")),
        "n_positive": len(positives),
        "n_no_answer": len(no_answer),
    }
    if answer_rows:
        out.update(
            {
                "cite_existence": _avg("cite_existence"),
                "cite_precision": _avg("cite_precision"),
                "must_contain": _avg("must_contain"),
                "no_answer_success_rate": _avg("no_answer_ok"),
                "violations": sum(int(r.get("violations", 0)) for r in per_item),
            }
        )
    if no_answer and any(r.get("stopped_by") or r.get("abstain_decision") for r in no_answer):
        abstained = [
            r
            for r in no_answer
            if r.get("stopped_by") in {"no_evidence_abstain", "no_chunks"}
            or r.get("abstain_decision") in {"no_evidence", "no_chunks"}
        ]
        out["no_answer_abstain_rate"] = round(len(abstained) / len(no_answer), 3)
    decisions: dict[str, int] = {}
    for r in per_item:
        decision = r.get("abstain_decision")
        if isinstance(decision, str) and decision:
            decisions[decision] = decisions.get(decision, 0) + 1
    if decisions:
        out["abstain_decisions"] = decisions
    judge_keys = ("faithful", "complete", "concise")
    judges = [r.get("judge") for r in per_item if isinstance(r.get("judge"), dict) and "faithful" in r["judge"]]
    if judges:
        for k in judge_keys:
            out[f"judge_{k}"] = round(mean(j[k] for j in judges), 2)
    return out


def _has_relevant_paper(rec: dict) -> bool:
    return bool(rec.get("expected_relevant_paper_count", 0))


def _looks_like_insufficient_evidence(answer: str) -> bool:
    low = (answer or "").lower()
    hints = (
        "does not contain",
        "does not mention",
        "not contain",
        "not provided",
        "cannot answer",
        "can't answer",
        "insufficient evidence",
        "evidence is insufficient",
        "未在",
        "没有",
        "无法回答",
    )
    return any(hint in low for hint in hints)


if __name__ == "__main__":
    sys.exit(run())
