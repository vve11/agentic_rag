"""LangChain tool wrappers around the standalone paper_rag package.

The DeerFlow Harness owns agent runtime concerns; the standalone paper_rag
package owns parsing, retrieval, QA, wiki, and citation behavior. This module is
only an adapter between those two layers.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from langchain.tools import tool


def _ensure_paper_rag_importable() -> None:
    """Find paper_rag when it is checked out beside, above, or inside DeerFlow."""
    try:
        import paper_rag  # noqa: F401

        return
    except ImportError:
        pass

    candidates: list[Path] = []
    if home := os.environ.get("PAPER_RAG_HOME"):
        root = Path(home).expanduser().resolve()
        candidates.extend([root / "src", root])

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.extend([
            parent / "src",
            parent / "paper_rag" / "src",
            parent / "paper-rag-agent" / "src",
        ])

    for candidate in candidates:
        if (candidate / "paper_rag").is_dir():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            return


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


@tool("paper_qa", parse_docstring=True)
def paper_qa_tool(question: str, paper_ids: str | None = None) -> str:
    """Answer a research question using the indexed paper corpus.

    Use this tool for paper, arXiv, DOI, academic literature, method,
    experiment, and citation questions. The tool runs its own Agentic RAG loop
    and returns an answer grounded in retrieved chunks.

    Args:
        question: Natural-language research question.
        paper_ids: Optional comma-separated paper ids to restrict retrieval.
    """
    _ensure_paper_rag_importable()
    from paper_rag.tools._schema import PaperQAInput
    from paper_rag.tools.paper_qa import paper_qa

    out = paper_qa(PaperQAInput(question=question, paper_ids=_split_csv(paper_ids)))
    chunks = [
        {key: chunk.get(key) for key in ("chunk_id", "paper_id", "section", "modality", "text")}
        for chunk in out.get("chunks", [])[:8]
    ]
    return _json_dumps({
        "answer": out.get("answer", ""),
        "citations": out.get("citations", []),
        "abstain": out.get("abstain"),
        "trace_id": out.get("trace_id"),
        "chunks": chunks,
    })


@tool("paper_search", parse_docstring=True)
def paper_search_tool(query: str, top_k: int = 8) -> str:
    """Find indexed papers relevant to a query.

    Use this as a lightweight discovery step before choosing a paper id for
    deeper QA or section reading.

    Args:
        query: Search query.
        top_k: Maximum number of papers to return.
    """
    _ensure_paper_rag_importable()
    from paper_rag.tools._schema import PaperSearchInput
    from paper_rag.tools.paper_search import paper_search

    return _json_dumps(paper_search(PaperSearchInput(query=query, top_k=top_k)))


@tool("paper_section", parse_docstring=True)
def paper_section_tool(paper_id: str, section_name: str) -> str:
    """Retrieve a named section from one indexed paper.

    Use this when the user asks for a specific paper section such as method,
    experiments, limitations, or conclusion.

    Args:
        paper_id: Paper id, for example arxiv:2310.11511.
        section_name: Case-insensitive section name or substring.
    """
    _ensure_paper_rag_importable()
    from paper_rag.tools._schema import PaperSectionInput
    from paper_rag.tools.paper_section import paper_section

    return _json_dumps(paper_section(PaperSectionInput(paper_id=paper_id, section_name=section_name)))


@tool("paper_compare", parse_docstring=True)
def paper_compare_tool(paper_ids: str, dimensions: str = "motivation,method,results,limitations") -> str:
    """Compare multiple indexed papers across selected dimensions.

    Keep this tool scoped: compare a small set of papers and a small number of
    dimensions so the agent does not create an expensive uncontrolled loop.

    Args:
        paper_ids: Comma-separated paper ids.
        dimensions: Comma-separated comparison dimensions.
    """
    _ensure_paper_rag_importable()
    from paper_rag.tools._schema import PaperCompareInput
    from paper_rag.tools.paper_compare import paper_compare

    parsed_ids = _split_csv(paper_ids) or []
    parsed_dimensions = _split_csv(dimensions) or []
    return _json_dumps(paper_compare(PaperCompareInput(paper_ids=parsed_ids, dimensions=parsed_dimensions)))


@tool("wiki_lookup", parse_docstring=True)
def wiki_lookup_tool(concept: str) -> str:
    """Look up a concept in the paper wiki.

    Use this for cached concept definitions, aliases, related papers, open
    problems, and review notes generated from the indexed corpus.

    Args:
        concept: Concept name to look up.
    """
    _ensure_paper_rag_importable()
    from paper_rag.tools._schema import WikiLookupInput
    from paper_rag.tools.wiki_lookup import wiki_lookup

    return _json_dumps(wiki_lookup(WikiLookupInput(concept=concept)))


@tool("export_bibtex", parse_docstring=True)
def export_bibtex_tool(paper_ids: str) -> str:
    """Export metadata for indexed papers as BibTeX.

    Use this after a research session to assemble references for a report,
    paper note, slide deck, or literature review.

    Args:
        paper_ids: Comma-separated paper ids.
    """
    _ensure_paper_rag_importable()
    from paper_rag.tools.bibtex_export import BibtexExportInput, export_bibtex

    return _json_dumps(export_bibtex(BibtexExportInput(paper_ids=_split_csv(paper_ids) or [])))


__all__ = [
    "paper_qa_tool",
    "paper_search_tool",
    "paper_section_tool",
    "paper_compare_tool",
    "wiki_lookup_tool",
    "export_bibtex_tool",
]
