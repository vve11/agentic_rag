from __future__ import annotations

import json
import os
import sys
from typing import Any

STATUS_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
    "additionalProperties": False,
}
WRITE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"note": {"type": "string"}},
    "required": ["note"],
    "additionalProperties": False,
}
STRUCTURED_OUTPUT_SCHEMA = {"type": "object", "additionalProperties": True}


def respond(request_id: Any, result: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}) + "\n")
    sys.stdout.flush()


def error(request_id: Any, message: str) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": message},
            }
        )
        + "\n"
    )
    sys.stdout.flush()


def audit(tool_name: str, args: dict[str, Any], meta: dict[str, Any]) -> None:
    audit_path = os.environ.get("PAPER_RAG_PRIVATE_AUDIT_PATH")
    if not audit_path:
        return
    with open(audit_path, "a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "tool_name": tool_name,
                    "received_arguments": args,
                    "received_meta": meta,
                    "receiver": "python",
                }
            )
            + "\n"
        )


def tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "fixture_status",
            "description": "Private Python fixture status tool.",
            "inputSchema": STATUS_INPUT_SCHEMA,
            "outputSchema": STRUCTURED_OUTPUT_SCHEMA,
        },
        {
            "name": "write_probe",
            "description": "Private Python fixture write probe.",
            "inputSchema": WRITE_INPUT_SCHEMA,
            "outputSchema": STRUCTURED_OUTPUT_SCHEMA,
        },
    ]


def call_tool(params: dict[str, Any]) -> dict[str, Any]:
    tool_name = params["name"]
    args = params.get("arguments") or {}
    meta = params.get("_meta") or {}
    audit(tool_name, args, meta)

    if tool_name == "fixture_status":
        structured = {
            "ok": True,
            "received_arguments": args,
            "received_meta": meta,
            "has_test_credential": bool(os.environ.get("PAPER_RAG_TEST_TOKEN")),
        }
        return {
            "content": [{"type": "text", "text": json.dumps({"ok": True})}],
            "structuredContent": structured,
        }
    if tool_name == "write_probe":
        structured = {
            "approved": True,
            "received_arguments": args,
            "received_meta": meta,
        }
        return {
            "content": [{"type": "text", "text": json.dumps({"approved": True})}],
            "structuredContent": structured,
        }
    raise ValueError(f"unknown fixture tool: {tool_name}")


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None:
        return

    if method == "initialize":
        params = message.get("params") or {}
        respond(
            request_id,
            {
                "protocolVersion": params.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "paper-rag-python-fixture", "version": "0.0.0"},
            },
        )
        return
    if method == "tools/list":
        respond(request_id, {"tools": tools()})
        return
    if method == "tools/call":
        respond(request_id, call_tool(message.get("params") or {}))
        return
    if method == "ping":
        respond(request_id, {})
        return
    error(request_id, f"unsupported method: {method}")


for line in sys.stdin:
    if not line.strip():
        continue
    try:
        handle(json.loads(line))
    except Exception as exc:  # pragma: no cover - fixture diagnostics only
        request = json.loads(line)
        error(request.get("id"), str(exc))
