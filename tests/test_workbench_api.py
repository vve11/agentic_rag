from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def _settings(tmp_path: Path):
    from paper_rag.workbench.settings import WorkbenchSettings

    return WorkbenchSettings(
        actor_id="workbench",
        toolset="research",
        dsh_url="http://127.0.0.1:3080",
        credentials_path=tmp_path / ".credentials.yaml",
        artifact_root=tmp_path / "artifacts",
        import_root=tmp_path / "imports",
        openai_base_url="https://api.deepseek.com",
        chat_model="deepseek-v4-flash",
        small_model="deepseek-v4-flash",
    )


def test_health_reports_workbench_model_and_dsh_url(tmp_path):
    from paper_rag.workbench.api import create_app

    client = TestClient(create_app(_settings(tmp_path), call_tool_fn=lambda *_args: {}))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "paper-rag-workbench",
        "dsh_url": "http://127.0.0.1:3080",
        "models": {
            "chat_model": "deepseek-v4-flash",
            "small_model": "deepseek-v4-flash",
        },
    }


def test_status_endpoint_returns_mcp_structured_content(tmp_path):
    from paper_rag.workbench.api import create_app

    seen: dict[str, Any] = {}

    def fake_call_tool(name, args, ctx):
        seen.update(
            name=name,
            args=args,
            actor_id=ctx.actor_id,
            toolset=ctx.config.toolset,
            conversation_id=ctx.conversation_id,
            tool_call_id=ctx.tool_call_id,
        )
        return {
            "structuredContent": {
                "ok": True,
                "tool": "paper_status",
                "evidence_role": "metadata",
                "warnings": [],
                "data": {
                    "sqlite": {"paper_count": 2, "chunk_count": 30, "available": True},
                    "llm": {"chat_model": "deepseek-v4-flash", "configured": True},
                },
            }
        }

    client = TestClient(create_app(_settings(tmp_path), call_tool_fn=fake_call_tool))

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["tool"] == "paper_status"
    assert response.json()["data"]["sqlite"]["paper_count"] == 2
    assert seen == {
        "name": "paper_status",
        "args": {},
        "actor_id": "workbench",
        "toolset": "research",
        "conversation_id": "workbench",
        "tool_call_id": "workbench-paper_status",
    }
