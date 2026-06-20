"""Tests for retrieve/rag pure-logic pieces (no qdrant/llm/embed)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_rrf_basic():
    from paper_rag.retrieve.hybrid import rrf_fuse

    a = [{"chunk_id": "x"}, {"chunk_id": "y"}, {"chunk_id": "z"}]
    b = [{"chunk_id": "y"}, {"chunk_id": "w"}, {"chunk_id": "x"}]
    fused = rrf_fuse([a, b], k=60)
    ids = [d["chunk_id"] for d in fused]
    assert ids[0] in {"x", "y"}
    assert "w" in ids
    by_id = {d["chunk_id"]: d for d in fused}
    assert by_id["y"]["score_rrf"] > by_id["w"]["score_rrf"]


def test_rrf_handles_empty():
    from paper_rag.retrieve.hybrid import rrf_fuse

    assert rrf_fuse([], k=60) == []
    assert rrf_fuse([[]], k=60) == []


def test_bm25_tokenize_zh_en():
    from paper_rag.retrieve.sparse_bm25 import _tokenize

    toks = _tokenize("Hello 世界 BM25_score 你好123")
    assert "hello" in toks
    assert "世" in toks and "界" in toks
    assert "你" in toks and "好" in toks
    assert "bm25_score" in toks
    assert "123" in toks


def test_infer_modalities_formula_table():
    from paper_rag.retrieve.pipeline import infer_modalities

    assert infer_modalities("解释这个公式的推导") == ["formula"]
    assert "table" in infer_modalities("summarize the comparison table")
    assert infer_modalities("What is Self-RAG?") == []


def test_retrieve_round_adds_modality_search():
    from paper_rag.retrieve import pipeline

    calls = []

    def fake_hybrid(query, *, top_k=None, paper_ids=None, modality=None):
        calls.append((query, modality))
        suffix = modality or "text"
        return [{"chunk_id": f"{query}-{suffix}", "score_rrf": 1.0, "modality": suffix}]

    old_hybrid = pipeline.hybrid_search
    old_rerank = pipeline._rerank
    pipeline.hybrid_search = fake_hybrid
    pipeline._rerank = lambda query, candidates, top_k=None: candidates[:top_k]
    try:
        chunks, _ = pipeline.retrieve_round_with_rewrite(
            "解释这个公式",
            ["p1"],
            5,
            rewrite_fn=lambda q: {"dense_queries": ["q1"]},
        )
    finally:
        pipeline.hybrid_search = old_hybrid
        pipeline._rerank = old_rerank

    assert ("q1", None) in calls
    assert ("q1", "formula") in calls
    assert {c["modality"] for c in chunks} == {"text", "formula"}


def test_diversify_by_paper_promotes_other_papers():
    from paper_rag.retrieve.pipeline import _diversify_by_paper

    chunks = [
        {"chunk_id": f"a{i}", "paper_id": "paper-a"}
        for i in range(6)
    ] + [
        {"chunk_id": "b1", "paper_id": "paper-b"},
        {"chunk_id": "c1", "paper_id": "paper-c"},
    ]

    out = _diversify_by_paper(chunks, top_k=6)
    ids = [c["chunk_id"] for c in out]

    assert ids[:2] == ["a0", "a1"]
    assert "b1" in ids
    assert "c1" in ids


def test_query_rewrite_heuristic_expands_original_alias():
    from paper_rag.rag import query_rewrite

    old_lookup = query_rewrite._papers_for_alias
    query_rewrite._papers_for_alias = lambda alias: [
        {
            "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "year": 2020,
            "arxiv_id": "2005.11401",
        },
        {
            "title": "Retrieval-Augmented Generation for Large Language Models: A Survey",
            "year": 2023,
            "arxiv_id": "2312.10997",
        },
    ] if alias == "RAG" else []
    try:
        variants = query_rewrite._heuristic_variants(
            "How do Self-RAG and the original RAG differ?"
        )
    finally:
        query_rewrite._papers_for_alias = old_lookup

    assert variants[0] == "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
    assert "RAG" in query_rewrite._aliases_for_title(
        "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
    )


def test_query_rewrite_heuristic_expands_retrieval_metric_query():
    from paper_rag.rag.query_rewrite import _heuristic_variants

    variants = _heuristic_variants(
        "Why is recall@k more important than precision@k for the retrieval stage?"
    )

    assert any("RAG retrieval evaluation metrics" in v for v in variants)
