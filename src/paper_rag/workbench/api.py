from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from starlette.responses import StreamingResponse

from paper_rag.mcp.context import McpRequestContext, McpServerConfig
from paper_rag.mcp.registry import call_tool

from .approval import build_request_boundary, validate_candidate_ingest_approval
from .credentials import credential_status
from .diagnostics import build_index_health
from .read_store import WorkbenchReadStore
from .schemas import (
    CandidateIngestRequest,
    DiscoverRequest,
    DshHandoffRequest,
    QaRequest,
    SearchRequest,
    SectionRequest,
)
from .settings import WorkbenchSettings

CallTool = Callable[[str, dict[str, Any] | None, McpRequestContext], dict[str, Any]]
IndexHealthBuilder = Callable[[WorkbenchSettings], dict[str, Any]]
QaStreamer = Callable[..., AsyncIterator[dict[str, Any]]]


def create_app(
    settings: WorkbenchSettings | None = None,
    *,
    call_tool_fn: CallTool = call_tool,
    index_health_fn: IndexHealthBuilder | None = None,
    read_store: WorkbenchReadStore | None = None,
    stream_answer_fn: QaStreamer | None = None,
) -> FastAPI:
    app_settings = settings or WorkbenchSettings.from_env()
    store = read_store or WorkbenchReadStore()
    if stream_answer_fn is None:
        from paper_rag.rag.async_api import stream_answer_async

        stream_answer_fn = stream_answer_async
    index_health_builder = index_health_fn or (
        lambda current_settings: build_index_health(
            current_settings,
            read_store=store,
        )
    )
    app = FastAPI(title="Paper RAG Workbench", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "paper-rag-workbench",
            "dsh_url": app_settings.dsh_url,
            "models": {
                "chat_model": app_settings.chat_model,
                "small_model": app_settings.small_model,
            },
        }

    @app.get("/api/health/index")
    def index_health() -> dict[str, Any]:
        return index_health_builder(app_settings)

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        envelope = _call("paper_status", {}, app_settings, call_tool_fn)
        data = envelope.setdefault("data", {})
        data["workbench"] = {
            "credentials": credential_status(
                credentials_path=app_settings.credentials_path
            ).as_dict()
        }
        return envelope

    @app.get("/api/papers")
    def papers(limit: int = 20) -> dict[str, Any]:
        return _call("paper_list", {"limit": limit}, app_settings, call_tool_fn)

    @app.get("/api/papers/{paper_id:path}")
    def paper_detail(paper_id: str) -> dict[str, Any]:
        try:
            detail = store.paper_detail(paper_id)
        except ValueError as exc:
            raise _http_error(400, "BAD_REQUEST", str(exc)) from exc
        if detail is None:
            raise _http_error(404, "NOT_FOUND", f"Paper not found: {paper_id}")
        return detail

    @app.get("/api/chunks/{chunk_id}")
    def chunk_detail(chunk_id: str) -> dict[str, Any]:
        try:
            detail = store.chunk_detail(chunk_id)
        except ValueError as exc:
            raise _http_error(400, "BAD_REQUEST", str(exc)) from exc
        if detail is None:
            raise _http_error(404, "NOT_FOUND", f"Chunk not found: {chunk_id}")
        return detail

    @app.post("/api/search")
    def search(payload: SearchRequest) -> dict[str, Any]:
        return _call(
            "paper_search",
            payload.model_dump(exclude_none=True),
            app_settings,
            call_tool_fn,
        )

    @app.post("/api/qa")
    def qa(payload: QaRequest) -> dict[str, Any]:
        return _call(
            "paper_qa",
            payload.model_dump(exclude_none=True),
            app_settings,
            call_tool_fn,
        )

    @app.post("/api/qa/stream")
    async def qa_stream(payload: QaRequest) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            async for event in stream_answer_fn(
                payload.question,
                paper_ids=payload.paper_ids,
                conversation_id="workbench",
                user_id=app_settings.actor_id,
                resolved_question=payload.resolved_question,
            ):
                yield _sse_frame(event)

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/api/section")
    def section(payload: SectionRequest) -> dict[str, Any]:
        return _call(
            "paper_section",
            payload.model_dump(exclude_none=True),
            app_settings,
            call_tool_fn,
        )

    @app.post("/api/discover")
    def discover(payload: DiscoverRequest) -> dict[str, Any]:
        return _call(
            "paper_discover",
            payload.model_dump(exclude_none=True),
            app_settings,
            call_tool_fn,
        )

    @app.get("/api/discovery-runs/{run_id}")
    def discovery_run(run_id: int) -> dict[str, Any]:
        return _call("discovery_run_get", {"run_id": run_id}, app_settings, call_tool_fn)

    @app.post("/api/ingest/candidates")
    def ingest_candidates(payload: CandidateIngestRequest) -> dict[str, Any]:
        approval = validate_candidate_ingest_approval(payload)
        boundary = build_request_boundary("discovery_candidate_ingest", approval)
        args = payload.model_dump(exclude={"approval"}, exclude_none=True)
        return _call(
            "discovery_candidate_ingest",
            args,
            app_settings,
            call_tool_fn,
            boundary=boundary,
        )

    @app.post("/api/dsh/handoff")
    def dsh_handoff(payload: DshHandoffRequest) -> dict[str, Any]:
        return {
            "dsh_url": app_settings.dsh_url,
            "prompt": _build_dsh_prompt(payload),
        }

    return app


def _context(
    settings: WorkbenchSettings,
    *,
    tool_name: str,
    boundary: str | None = None,
) -> McpRequestContext:
    return McpRequestContext(
        config=McpServerConfig(
            toolset=settings.toolset,
            actor_id=settings.actor_id,
            artifact_root=settings.artifact_root,
            import_root=settings.import_root,
        ),
        conversation_id="workbench",
        tool_call_id=f"workbench-{tool_name}",
        request_boundary_id=boundary,
        caller="workbench",
    )


def _call(
    tool_name: str,
    args: dict[str, Any],
    settings: WorkbenchSettings,
    call_tool_fn: CallTool,
    *,
    boundary: str | None = None,
) -> dict[str, Any]:
    result = call_tool_fn(tool_name, args, _context(settings, tool_name=tool_name, boundary=boundary))
    return mcp_envelope(result, tool=tool_name)


def _sse_frame(event: dict[str, Any]) -> str:
    name = str(event.get("event") or "message")
    data = event.get("data")
    payload = json.dumps(data if isinstance(data, dict) else {}, ensure_ascii=False)
    return f"event: {name}\ndata: {payload}\n\n"


def mcp_envelope(result: dict[str, Any], *, tool: str) -> dict[str, Any]:
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    raise HTTPException(
        status_code=502,
        detail={
            "ok": False,
            "tool": tool,
            "error": {
                "code": "BAD_GATEWAY",
                "message": "Paper RAG tool returned no structuredContent",
                "retryable": False,
            },
        },
    )


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "retryable": False,
            },
        },
    )


def _build_dsh_prompt(payload: DshHandoffRequest) -> str:
    papers = ", ".join(payload.paper_ids) if payload.paper_ids else "未指定"
    chunks = ", ".join(payload.chunk_ids) if payload.chunk_ids else "未指定"
    return (
        "基于 Paper RAG Workbench 中选定的论文/证据继续研究：\n"
        f"- Source: {payload.source}\n"
        f"- Papers: {papers}\n"
        f"- Chunks: {chunks}\n"
        f"- Question: {payload.question.strip()}\n"
        "请使用 Paper RAG 工具回答，并保留证据引用。"
    )
