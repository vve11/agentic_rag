from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException

from paper_rag.mcp.context import McpRequestContext, McpServerConfig
from paper_rag.mcp.registry import call_tool

from .approval import build_request_boundary, validate_candidate_ingest_approval
from .credentials import credential_status
from .schemas import (
    CandidateIngestRequest,
    DiscoverRequest,
    QaRequest,
    SearchRequest,
    SectionRequest,
)
from .settings import WorkbenchSettings

CallTool = Callable[[str, dict[str, Any] | None, McpRequestContext], dict[str, Any]]


def create_app(
    settings: WorkbenchSettings | None = None,
    *,
    call_tool_fn: CallTool = call_tool,
) -> FastAPI:
    app_settings = settings or WorkbenchSettings.from_env()
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
