"""MCP tool registry and read-only Paper RAG handlers."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .context import McpRequestContext, McpServerConfig
from .errors import McpToolError, map_exception, validation_error
from .presenters import (
    MAX_SNIPPET_CHARS,
    bounded_chunks,
    error_result,
    success_result,
    truncate_text,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaperStatusArgs(StrictModel):
    pass


class PaperListArgs(StrictModel):
    limit: int = Field(20, ge=1, le=100)


class PaperSearchArgs(StrictModel):
    query: str
    top_k: int = Field(8, ge=1, le=30)
    year_min: int | None = None
    year_max: int | None = None


class PaperQAArgs(StrictModel):
    question: str
    paper_ids: list[str] | None = None
    resolved_question: str | None = None
    top_k: int = Field(8, ge=1, le=20)


class PaperSectionArgs(StrictModel):
    paper_id: str
    section_name: str


class PaperCompareArgs(StrictModel):
    paper_ids: list[str] = Field(..., min_length=1, max_length=4)
    dimensions: list[str] = Field(..., min_length=1, max_length=4)


class WikiLookupArgs(StrictModel):
    concept: str


class PaperDiscoverArgs(StrictModel):
    topic: str
    max_candidates: int = Field(10, ge=1, le=20)
    sources: list[str] | None = None


class DiscoveryRunGetArgs(StrictModel):
    run_id: int = Field(..., ge=1)


class PaperIngestArgs(StrictModel):
    arxiv_id: str | None = None
    pdf_url: str | None = None
    pdf_path: str | None = None
    title_hint: str | None = None
    force: bool = False

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "PaperIngestArgs":
        sources = [self.arxiv_id, self.pdf_url, self.pdf_path]
        if sum(1 for value in sources if value) != 1:
            raise ValueError("provide exactly one of arxiv_id, pdf_url, or pdf_path")
        return self


class DiscoveryCandidateIngestArgs(StrictModel):
    candidate_ids: list[int] = Field(..., min_length=1, max_length=5)
    force: bool = False


class WikiGenerateArgs(StrictModel):
    paper_id: str
    force: bool = False


class ExportBibtexArgs(StrictModel):
    paper_ids: list[str] = Field(..., min_length=1, max_length=100)


class PaperDeliverArgs(StrictModel):
    format: str
    paper_ids: list[str] = Field(..., min_length=1, max_length=5)
    title: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class PlaceholderArgs(StrictModel):
    pass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[StrictModel]
    evidence_role: str
    handler: Callable[[StrictModel, McpRequestContext], dict[str, Any]] | None

    def as_mcp_tool(self) -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        schema["additionalProperties"] = False
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": schema,
            "outputSchema": OUTPUT_SCHEMA,
        }


OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["ok", "tool"],
    "properties": {
        "ok": {"type": "boolean"},
        "tool": {"type": "string"},
        "trace_id": {"type": ["string", "null"]},
        "data": {"type": "object"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "evidence_role": {"type": "string"},
        "truncated": {"type": "boolean"},
        "error": {"type": "object"},
    },
    "additionalProperties": True,
}

READONLY_TOOL_NAMES = (
    "paper_status",
    "paper_list",
    "paper_search",
    "paper_qa",
    "paper_section",
    "paper_compare",
    "wiki_lookup",
)
RESEARCH_TOOL_NAMES = READONLY_TOOL_NAMES + (
    "paper_discover",
    "discovery_run_get",
    "paper_ingest",
    "discovery_candidate_ingest",
    "wiki_generate",
    "export_bibtex",
    "paper_deliver",
)
FULL_TOOL_NAMES = RESEARCH_TOOL_NAMES + (
    "subscription_list",
    "subscription_add",
    "subscription_toggle",
    "subscription_delete",
    "inbox_list",
    "inbox_mark_read",
    "inbox_dismiss",
    "feedback_record",
    "digest_run",
    "stale_scan",
)


def list_tools(config: McpServerConfig | None = None) -> list[dict[str, Any]]:
    config = config or McpServerConfig.from_env()
    return [_TOOLS[name].as_mcp_tool() for name in _names_for_toolset(config.toolset)]


def call_tool(name: str, args: dict[str, Any] | None, ctx: McpRequestContext) -> dict[str, Any]:
    if name not in _names_for_toolset(ctx.config.toolset):
        return error_result(
            name,
            code="NOT_FOUND",
            message=f"tool is not enabled for toolset {ctx.config.toolset}: {name}",
        )
    tool = _TOOLS.get(name)
    if tool is None or tool.handler is None:
        return error_result(name, code="NOT_FOUND", message=f"tool is not implemented: {name}")
    try:
        payload = tool.input_model.model_validate(args or {})
        data = tool.handler(payload, ctx)
        trace_id = data.pop("trace_id", None)
        truncated = bool(data.get("truncated", False))
        return success_result(
            name,
            data,
            evidence_role=tool.evidence_role,
            trace_id=trace_id,
            truncated=truncated,
        )
    except ValidationError as exc:
        return _domain_error(name, validation_error(exc))
    except Exception as exc:
        return _domain_error(name, map_exception(exc))


def _domain_error(name: str, exc: McpToolError) -> dict[str, Any]:
    return error_result(
        name,
        code=exc.code,
        message=str(exc),
        retryable=exc.retryable,
        details=exc.details,
    )


def _names_for_toolset(toolset: str) -> tuple[str, ...]:
    if toolset == "readonly":
        return READONLY_TOOL_NAMES
    if toolset == "research":
        return RESEARCH_TOOL_NAMES
    if toolset == "full":
        return FULL_TOOL_NAMES
    raise ValueError(f"invalid toolset: {toolset}")


def _paper_status(_payload: StrictModel, _ctx: McpRequestContext) -> dict[str, Any]:
    from sqlmodel import Session, select

    from .. import config as cfg
    from ..store.sqlite_store import Chunk, Paper, get_engine

    config = cfg.load()
    engine = get_engine()
    with Session(engine) as session:
        paper_count = len(list(session.exec(select(Paper.paper_id))))
        chunk_count = len(list(session.exec(select(Chunk.chunk_id))))
    return {
        "sqlite": {
            "path": config.paths.sqlite_path,
            "available": True,
            "paper_count": paper_count,
            "chunk_count": chunk_count,
        },
        "qdrant": {
            "url": config.qdrant.url,
            "local_path": config.qdrant.local_path,
            "collection_chunks": config.qdrant.collection_chunks,
            "collection_wiki": config.qdrant.collection_wiki,
        },
        "llm": {
            "base_url": config.llm.base_url,
            "chat_model": config.llm.chat_model,
            "configured": bool(config.llm.base_url and config.llm.chat_model),
        },
        "wiki": {"enabled": bool(config.wiki.enabled)},
    }


def _paper_list(payload: StrictModel, _ctx: McpRequestContext) -> dict[str, Any]:
    from sqlmodel import Session, select

    from ..store.sqlite_store import Chunk, Paper, get_engine

    typed = _cast(PaperListArgs, payload)
    with Session(get_engine()) as session:
        papers = list(session.exec(select(Paper).order_by(Paper.updated_at.desc()).limit(typed.limit)))
        chunks = list(session.exec(select(Chunk.paper_id).where(Chunk.paper_id.in_([p.paper_id for p in papers]))))
    counts: dict[str, int] = {}
    for paper_id in chunks:
        counts[str(paper_id)] = counts.get(str(paper_id), 0) + 1
    return {
        "count": len(papers),
        "papers": [
            {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "arxiv_id": paper.arxiv_id,
                "chunk_count": counts.get(paper.paper_id, 0),
                "ingested_at": paper.updated_at.isoformat(),
            }
            for paper in papers
        ],
    }


def _paper_search(payload: StrictModel, _ctx: McpRequestContext) -> dict[str, Any]:
    from ..tools import paper_search as paper_search_module
    from ..tools._schema import PaperSearchInput

    typed = _cast(PaperSearchArgs, payload)
    results = paper_search_module.paper_search(PaperSearchInput(**typed.model_dump()))
    truncated = False
    bounded = []
    for result in results:
        item = dict(result)
        item["snippet"], did_truncate = truncate_text(
            item.get("snippet", ""), MAX_SNIPPET_CHARS
        )
        truncated = truncated or did_truncate
        bounded.append(item)
    return {"results": bounded, "count": len(bounded), "truncated": truncated}


def _paper_qa(payload: StrictModel, ctx: McpRequestContext) -> dict[str, Any]:
    from ..tools import paper_qa as paper_qa_module
    from ..tools._schema import PaperQAInput

    typed = _cast(PaperQAArgs, payload)
    resolved = typed.resolved_question or typed.question
    raw = paper_qa_module.paper_qa(
        PaperQAInput(
            question=typed.question,
            paper_ids=typed.paper_ids,
            conversation_id=ctx.conversation_id,
            user_id=ctx.actor_id,
            resolved_question=resolved,
            top_k=typed.top_k,
        )
    )
    trace = raw.get("trace") or {}
    chunks, truncated = bounded_chunks(list(raw.get("chunks") or []))
    query_resolution = trace.get("query_resolution") or {"effective_question": resolved}
    return {
        "answer": raw.get("answer", ""),
        "citations": list(raw.get("citations") or []),
        "chunks": chunks,
        "abstain": trace.get("abstain") or {},
        "query_resolution": query_resolution,
        "trace_id": trace.get("trace_id"),
        "truncated": truncated,
    }


def _paper_section(payload: StrictModel, _ctx: McpRequestContext) -> dict[str, Any]:
    from ..tools import paper_section as paper_section_module
    from ..tools._schema import PaperSectionInput

    typed = _cast(PaperSectionArgs, payload)
    raw = paper_section_module.paper_section(PaperSectionInput(**typed.model_dump()))
    chunks, truncated = bounded_chunks(list(raw.get("chunks") or []))
    return {**raw, "chunks": chunks, "truncated": truncated}


def _paper_compare(payload: StrictModel, ctx: McpRequestContext) -> dict[str, Any]:
    from ..rag import qa_agentic

    typed = _cast(PaperCompareArgs, payload)
    matrix: dict[str, dict[str, dict[str, Any]]] = {}
    truncated = False
    for paper_id in typed.paper_ids:
        matrix[paper_id] = {}
        for dimension in typed.dimensions:
            question = f"What is the {dimension} of this paper?"
            raw = qa_agentic.answer(
                question,
                paper_ids=[paper_id],
                conversation_id=ctx.conversation_id,
                user_id=ctx.actor_id,
                resolved_question=question,
            )
            chunks, chunks_truncated = bounded_chunks(list(raw.get("chunks") or []), text_limit=300)
            truncated = truncated or chunks_truncated
            matrix[paper_id][dimension] = {
                "answer": raw.get("answer", ""),
                "citations": list(raw.get("citations") or []),
                "chunks": chunks,
            }
    return {
        "papers": typed.paper_ids,
        "dimensions": typed.dimensions,
        "matrix": matrix,
        "truncated": truncated,
    }


def _wiki_lookup(payload: StrictModel, _ctx: McpRequestContext) -> dict[str, Any]:
    from ..tools import wiki_lookup as wiki_lookup_module
    from ..tools._schema import WikiLookupInput

    typed = _cast(WikiLookupArgs, payload)
    return wiki_lookup_module.wiki_lookup(WikiLookupInput(**typed.model_dump()))


def _paper_discover(payload: StrictModel, ctx: McpRequestContext) -> dict[str, Any]:
    from ..discovery import runner

    typed = _cast(PaperDiscoverArgs, payload)
    raw = runner.run_discovery(
        typed.topic,
        user_id=ctx.actor_id,
        source_names=typed.sources,
        max_candidates=typed.max_candidates,
    )
    candidates = []
    for candidate in raw.get("candidates") or []:
        candidates.append(
            {
                **candidate,
                "evidence_role": "discovery_only_not_answer_evidence",
            }
        )
    return {
        "run": raw.get("run") or {},
        "trace": raw.get("trace") or {},
        "candidates": candidates,
        "count": len(candidates),
    }


def _discovery_run_get(payload: StrictModel, ctx: McpRequestContext) -> dict[str, Any]:
    from ..discovery import store

    typed = _cast(DiscoveryRunGetArgs, payload)
    raw = store.get_run(typed.run_id, user_id=ctx.actor_id)
    return {
        **raw,
        "candidates": [
            {
                **candidate,
                "evidence_role": "discovery_only_not_answer_evidence",
            }
            for candidate in raw.get("candidates") or []
        ],
    }


def _paper_ingest(payload: StrictModel, ctx: McpRequestContext) -> dict[str, Any]:
    from ..tools import paper_index

    _require_write_boundary("paper_ingest", ctx)
    typed = _cast(PaperIngestArgs, payload)
    body = typed.model_dump()
    if typed.pdf_path:
        body["pdf_path"] = _resolve_import_pdf_path(typed.pdf_path, ctx)
    body["user_id"] = ctx.actor_id
    return paper_index.ingest(paper_index.PaperIngestInput(**body))


def _discovery_candidate_ingest(payload: StrictModel, ctx: McpRequestContext) -> dict[str, Any]:
    from ..discovery import runner

    _require_write_boundary("discovery_candidate_ingest", ctx)
    typed = _cast(DiscoveryCandidateIngestArgs, payload)
    results = [
        runner.ingest_candidate(candidate_id, user_id=ctx.actor_id, force=typed.force)
        for candidate_id in typed.candidate_ids
    ]
    return {"results": results, "count": len(results)}


def _wiki_generate(payload: StrictModel, ctx: McpRequestContext) -> dict[str, Any]:
    from ..wiki import triggers

    _require_write_boundary("wiki_generate", ctx)
    typed = _cast(WikiGenerateArgs, payload)
    return triggers.on_paper_indexed(typed.paper_id, force=typed.force)


def _export_bibtex(payload: StrictModel, _ctx: McpRequestContext) -> dict[str, Any]:
    from ..tools import bibtex_export

    typed = _cast(ExportBibtexArgs, payload)
    return bibtex_export.export_bibtex(bibtex_export.BibtexExportInput(**typed.model_dump()))


def _paper_deliver(payload: StrictModel, ctx: McpRequestContext) -> dict[str, Any]:
    from .artifacts import write_artifact

    _require_write_boundary("paper_deliver", ctx)
    typed = _cast(PaperDeliverArgs, payload)
    if ctx.config.artifact_root is None:
        raise McpToolError("UNAVAILABLE", "PAPER_RAG_ARTIFACT_ROOT is required for paper_deliver")
    deliver_dispatch = importlib.import_module("paper_rag.deliver.dispatch")
    result = deliver_dispatch.dispatch(
        typed.format,
        typed.paper_ids,
        title=typed.title,
        options=typed.options,
        user_id=ctx.actor_id,
    )
    artifact = write_artifact(
        ctx.config.artifact_root,
        tool="paper_deliver",
        filename=result.filename,
        content_bytes=result.content_bytes,
        content_type=result.content_type,
        metadata={
            "format": result.format,
            "paper_ids": typed.paper_ids,
            "title": typed.title,
            "request_boundary_id": ctx.request_boundary_id,
            "deliver": result.metadata,
        },
    )
    return {
        "artifact": artifact,
        "format": result.format,
        "content_type": result.content_type,
        "paper_count": len(typed.paper_ids),
    }


def _require_write_boundary(tool_name: str, ctx: McpRequestContext) -> None:
    if not ctx.request_boundary_id:
        raise McpToolError(
            "UNAVAILABLE",
            "DIRECT_USER_AUTHORITY_REQUIRED",
            details={"tool": tool_name},
        )


def _resolve_import_pdf_path(pdf_path: str, ctx: McpRequestContext) -> str:
    if ctx.config.import_root is None:
        raise McpToolError("UNAVAILABLE", "PAPER_RAG_IMPORT_ROOT is required for pdf_path ingest")
    root = ctx.config.import_root.resolve()
    candidate = Path(pdf_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"pdf_path not found: {pdf_path}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("pdf_path must stay under PAPER_RAG_IMPORT_ROOT") from exc
    if resolved.suffix.lower() != ".pdf":
        raise ValueError("pdf_path must point to a PDF")
    return str(resolved)


def _cast(model: type[StrictModel], payload: StrictModel) -> Any:
    if isinstance(payload, model):
        return payload
    return model.model_validate(payload.model_dump())


_TOOLS: dict[str, ToolDefinition] = {
    "paper_status": ToolDefinition(
        "paper_status",
        "Inspect the local Paper RAG corpus, config, and dependency status.",
        PaperStatusArgs,
        "metadata",
        _paper_status,
    ),
    "paper_list": ToolDefinition(
        "paper_list",
        "List papers already present in the local shared corpus.",
        PaperListArgs,
        "metadata",
        _paper_list,
    ),
    "paper_search": ToolDefinition(
        "paper_search",
        "Search indexed paper chunks and return bounded paper-level matches.",
        PaperSearchArgs,
        "indexed_chunks",
        _paper_search,
    ),
    "paper_qa": ToolDefinition(
        "paper_qa",
        "Answer a self-contained question from indexed paper chunks with citations.",
        PaperQAArgs,
        "indexed_chunks",
        _paper_qa,
    ),
    "paper_section": ToolDefinition(
        "paper_section",
        "Read a named section from an indexed paper.",
        PaperSectionArgs,
        "indexed_chunks",
        _paper_section,
    ),
    "paper_compare": ToolDefinition(
        "paper_compare",
        "Compare up to four indexed papers across up to four dimensions.",
        PaperCompareArgs,
        "indexed_chunks",
        _paper_compare,
    ),
    "wiki_lookup": ToolDefinition(
        "wiki_lookup",
        "Look up a Paper RAG wiki concept as background metadata, not final evidence.",
        WikiLookupArgs,
        "metadata",
        _wiki_lookup,
    ),
    "paper_discover": ToolDefinition(
        "paper_discover",
        "Discover candidate papers for a topic; candidates are not final answer evidence.",
        PaperDiscoverArgs,
        "discovery_only",
        _paper_discover,
    ),
    "discovery_run_get": ToolDefinition(
        "discovery_run_get",
        "Fetch a prior discovery run and its candidate-only results.",
        DiscoveryRunGetArgs,
        "discovery_only",
        _discovery_run_get,
    ),
    "paper_ingest": ToolDefinition(
        "paper_ingest",
        "Ingest one approved paper source into an isolated Paper RAG corpus.",
        PaperIngestArgs,
        "metadata",
        _paper_ingest,
    ),
    "discovery_candidate_ingest": ToolDefinition(
        "discovery_candidate_ingest",
        "Ingest up to five approved discovery candidates.",
        DiscoveryCandidateIngestArgs,
        "metadata",
        _discovery_candidate_ingest,
    ),
    "wiki_generate": ToolDefinition(
        "wiki_generate",
        "Generate or refresh wiki entries for one indexed paper.",
        WikiGenerateArgs,
        "metadata",
        _wiki_generate,
    ),
    "export_bibtex": ToolDefinition(
        "export_bibtex",
        "Export BibTeX for indexed papers without embedding binary content.",
        ExportBibtexArgs,
        "artifact",
        _export_bibtex,
    ),
    "paper_deliver": ToolDefinition(
        "paper_deliver",
        "Generate an approved deliverable artifact under the configured artifact root.",
        PaperDeliverArgs,
        "artifact",
        _paper_deliver,
    ),
}

for _name in FULL_TOOL_NAMES:
    _TOOLS.setdefault(
        _name,
        ToolDefinition(_name, f"{_name} is reserved for a later migration gate.", PlaceholderArgs, "none", None),
    )
