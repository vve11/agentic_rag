"""MCP tool registry and read-only Paper RAG handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
}

for _name in FULL_TOOL_NAMES:
    _TOOLS.setdefault(
        _name,
        ToolDefinition(_name, f"{_name} is reserved for a later migration gate.", PlaceholderArgs, "none", None),
    )
