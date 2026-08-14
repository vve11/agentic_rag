"""DeepSeek Harness migration gate helpers.

This script owns pre-G0/G0 bookkeeping: baseline fingerprints, legacy
capability matrix validation, diff hygiene, and structured report validation.
It intentionally keeps gate evidence machine-readable so later G1-G5 gates can
accumulate requirements instead of relying on hand-written summaries.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

LEGACY_TEST_FILES = (
    Path("tests/test_gateway_paper_rag.py"),
    Path("tests/test_middleware.py"),
    Path("tests/test_langgraph_middleware.py"),
)
QUALITY_BASELINE_COMMAND_IDS = (
    "eval-golden",
    "eval-golden-qa",
    "eval-citation-audit",
    "eval-claims",
    "verify-p0",
)
BASELINE_FINGERPRINT_PATHS = (
    Path("tests/eval/qa_set.golden.jsonl"),
    Path("tests/eval/gates.strict.json"),
    Path("tests/eval/qa_set.claims.jsonl"),
    Path("tests/eval/gates.claims.json"),
    Path("specs/20260813-deepseek-harness-migration/test/test-manifest.json"),
)
ALLOWED_LEGACY_CLASSIFICATIONS = {
    "host-specific-delete",
    "capability-replaced-by-broker-or-mcp",
    "still-required-and-moved",
}
TERMINAL_CASE_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"}
LIVE_REPORT_STATUSES = {"PASS", "FAIL", "BLOCKED"}
LIVE001_MODEL = "deepseek-v4-flash"
LIVE001_POSITIVE_QUESTION = "Which RAG variant retrieves differently for every output token?"
LIVE001_NEGATIVE_QUESTION = "What is my current bank account balance?"
LIVE001_PROMPT = f"""\
You are running Paper RAG migration LIVE-001.
Use only Paper RAG native tools. Do not use web search, shell, filesystem, or general knowledge.

Run exactly these checks:
1. Call paper_qa for this fixed indexed-paper question, with paper_ids ["arxiv:2005.11401"]:
   {LIVE001_POSITIVE_QUESTION}
2. Call paper_qa for this no-evidence question with no paper_ids:
   {LIVE001_NEGATIVE_QUESTION}

Return a concise final summary that states whether the first answer has at least one chunk citation
and whether the second answer abstained because the indexed paper corpus has no evidence.
"""
CASE_COVERAGE_BY_COMMAND = {
    "mcp-contract": (
        "MCP-001",
        "MCP-002",
        "MCP-003",
        "MCP-004",
        "MCP-005",
        "MCP-006",
        "MCP-007",
        "SEC-005",
    ),
    "mcp-tools": (
        "MCP-RO-001",
        "MCP-RO-002",
        "MCP-RO-003",
        "MCP-RO-004",
        "MCP-RO-005",
        "MCP-RO-006",
        "MCP-RO-007",
        "MCP-RO-008",
    ),
    "mcp-security": (
        "SEC-001",
        "SEC-002",
        "SEC-003",
        "SEC-004",
        "SEC-005",
    ),
    "mcp-parity": (
        "MCP-RO-004",
        "MCP-RO-005",
    ),
    "dsh-test": (
        "AGENT-001",
        "AGENT-002",
        "AGENT-003",
        "AGENT-004",
        "AGENT-005",
        "AGENT-006",
        "AGENT-007",
    ),
}


class GateError(RuntimeError):
    """Raised when migration evidence is missing or invalid."""


LiveRunner = Callable[..., dict[str, Any]]


def git_head(repo_root: Path) -> str:
    return _run_git(repo_root, "rev-parse", "HEAD").stdout.strip()


def git_dirty(repo_root: Path) -> bool:
    return bool(_run_git(repo_root, "status", "--porcelain").stdout.strip())


def collect_legacy_tests(repo_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rel in LEGACY_TEST_FILES:
        path = repo_root / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                out.append(
                    {
                        "file": rel.as_posix(),
                        "test_name": node.name,
                        "line": node.lineno,
                    }
                )
    return out


def validate_legacy_matrix(repo_root: Path, matrix_path: Path) -> dict[str, Any]:
    if not matrix_path.exists():
        raise GateError(f"legacy matrix not found: {matrix_path}")
    matrix = _read_json(matrix_path)
    entries = matrix.get("entries")
    if not isinstance(entries, list):
        raise GateError("legacy matrix must contain entries list")

    discovered = collect_legacy_tests(repo_root)
    expected = {(item["file"], item["test_name"]) for item in discovered}
    seen: set[tuple[str, str]] = set()
    by_file: dict[str, int] = {}
    by_classification: dict[str, int] = {}

    for i, entry in enumerate(entries):
        file = entry.get("file")
        test_name = entry.get("test_name")
        key = (file, test_name)
        if key not in expected:
            raise GateError(f"unknown legacy test at entries[{i}]: {file}::{test_name}")
        if key in seen:
            raise GateError(f"duplicate legacy test in matrix: {file}::{test_name}")
        seen.add(key)

        classification = entry.get("classification")
        if classification not in ALLOWED_LEGACY_CLASSIFICATIONS:
            raise GateError(
                f"invalid classification for {file}::{test_name}: {classification}"
            )
        if not str(entry.get("replacement", "")).strip():
            raise GateError(f"missing replacement evidence for {file}::{test_name}")
        if not str(entry.get("rationale", "")).strip():
            raise GateError(f"missing rationale for {file}::{test_name}")
        by_file[file] = by_file.get(file, 0) + 1
        by_classification[classification] = by_classification.get(classification, 0) + 1

    missing = sorted(expected - seen)
    extra = sorted(seen - expected)
    if missing:
        raise GateError(f"missing {len(missing)} legacy tests in matrix")
    if extra:
        raise GateError(f"extra {len(extra)} legacy tests in matrix")

    result = {
        "schema_version": matrix.get("schema_version", 1),
        "total": len(entries),
        "by_file": by_file,
        "by_classification": by_classification,
        "matrix_path": _relpath(matrix_path, repo_root),
    }
    return result


def freeze_baseline(
    repo_root: Path,
    spec_dir: Path,
    output_path: Path,
    *,
    require_clean: bool = True,
    execute_commands: bool = False,
) -> dict[str, Any]:
    if require_clean and git_dirty(repo_root):
        raise GateError("baseline freeze requires clean checkout")

    manifest_path = spec_dir / "test" / "test-manifest.json"
    manifest = _read_json(manifest_path)
    command_by_id = {
        command["id"]: command for command in manifest.get("owned_test_commands", [])
    }

    fingerprints = [_fingerprint(repo_root, rel) for rel in BASELINE_FINGERPRINT_PATHS]
    commands: list[dict[str, Any]] = []
    for command_id in QUALITY_BASELINE_COMMAND_IDS:
        command = command_by_id.get(command_id)
        if command is None:
            raise GateError(f"manifest missing quality command: {command_id}")
        record = {
            "id": command_id,
            "command": command["command"],
            "status": "NOT_RUN",
            "exit_code": None,
        }
        if execute_commands:
            executed = _run_shell_component(repo_root, command["command"])
            record.update(executed)
        commands.append(record)

    result = {
        "schema_version": 1,
        "feature": manifest["feature"],
        "commit": git_head(repo_root),
        "dirty": git_dirty(repo_root),
        "created_at": time.time(),
        "fingerprints": fingerprints,
        "commands": commands,
    }
    _write_json_atomic(output_path, result)
    return result


def validate_baseline(repo_root: Path, baseline_path: Path) -> dict[str, Any]:
    baseline = _read_json(baseline_path)
    mismatches: list[str] = []
    for item in baseline.get("fingerprints", []):
        current = _fingerprint(repo_root, Path(item["path"]))
        if current["sha256"] != item["sha256"]:
            mismatches.append(item["path"])
    if mismatches:
        raise GateError(f"baseline fingerprint mismatch: {', '.join(mismatches)}")
    return {
        "schema_version": 1,
        "baseline": _relpath(baseline_path, repo_root),
        "fingerprints": len(baseline.get("fingerprints", [])),
    }


def validate_report(
    repo_root: Path, manifest_path: Path, gate: str, report_path: Path
) -> dict[str, Any]:
    if not report_path.exists():
        raise GateError(f"report not found: {report_path}")
    manifest = _read_json(manifest_path)
    report = _read_json(report_path)
    if report.get("gate") != gate:
        raise GateError(f"report gate mismatch: expected {gate}, got {report.get('gate')}")
    if report.get("commit") != git_head(repo_root):
        raise GateError("report commit does not match HEAD")
    if report.get("dirty") is not False:
        raise GateError("report must record dirty=false")

    required = _required_cases_for_gate(manifest, gate)
    cases = report.get("cases", {})
    missing = [case_id for case_id in required if case_id not in cases]
    if missing:
        raise GateError(f"missing required cases: {', '.join(missing)}")
    not_pass = [
        case_id
        for case_id in required
        if cases.get(case_id, {}).get("status") != "PASS"
    ]
    if not_pass:
        raise GateError(f"required cases not PASS: {', '.join(not_pass)}")

    for case_id, case in cases.items():
        status = case.get("status")
        if status not in TERMINAL_CASE_STATUSES:
            raise GateError(f"invalid case status for {case_id}: {status}")

    return {
        "schema_version": 1,
        "gate": gate,
        "required_cases": len(required),
        "report": _relpath(report_path, repo_root),
    }


def validate_live(repo_root: Path, manifest_path: Path, gate: str) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    live_cases = [
        case for case in manifest.get("live_cases", [])
        if case.get("gate") == gate
    ]
    validated: list[str] = []
    now = time.time()
    for live_case in live_cases:
        case_id = live_case.get("id")
        report_path = repo_root / str(live_case.get("report", ""))
        if not report_path.exists():
            raise GateError(f"live report not found for {case_id}: {_relpath(report_path, repo_root)}")
        report = _read_json(report_path)
        if report.get("id") != case_id:
            raise GateError(f"live report id mismatch for {case_id}")
        if report.get("gate") != gate:
            raise GateError(f"live report gate mismatch for {case_id}")
        if report.get("commit") != git_head(repo_root):
            raise GateError(f"live report commit does not match HEAD for {case_id}")
        if report.get("status") != "PASS":
            raise GateError(f"live report is not PASS for {case_id}")
        if live_case.get("requires_authorization") and report.get("authorized") is not True:
            raise GateError(f"live report not authorized for {case_id}")
        max_age_hours = live_case.get("max_age_hours")
        if max_age_hours is not None:
            created_at = report.get("created_at")
            if not isinstance(created_at, (int, float)):
                raise GateError(f"live report missing created_at for {case_id}")
            if now - float(created_at) > float(max_age_hours) * 3600:
                raise GateError(f"live report expired for {case_id}")
        validated.append(str(case_id))
    return {
        "schema_version": 1,
        "gate": gate,
        "live_cases": validated,
    }


def run_live(
    repo_root: Path,
    manifest_path: Path,
    case_id: str,
    *,
    authorized_by: str | None = None,
    config_env: str | None = None,
    runner_registry: dict[str, LiveRunner] | None = None,
) -> dict[str, Any]:
    if git_dirty(repo_root):
        raise GateError("run-live requires clean checkout")
    manifest = _read_json(manifest_path)
    live_case = _live_case_for_id(manifest, case_id)
    effective_authorized_by = (authorized_by or os.environ.get("PAPER_RAG_LIVE_AUTHORIZED_BY", "")).strip()
    if live_case.get("requires_authorization") and not effective_authorized_by:
        raise GateError(
            f"live case {case_id} requires explicit authorization "
            "(pass --authorized-by or set PAPER_RAG_LIVE_AUTHORIZED_BY)"
        )

    registry = runner_registry if runner_registry is not None else LIVE_CASE_RUNNERS
    runner = registry.get(case_id)
    if runner is None:
        raise GateError(f"live runner not implemented for {case_id}")

    payload = runner(
        repo_root,
        live_case,
        config_env=config_env,
        authorized_by=effective_authorized_by,
    )
    status = payload.get("status")
    if status not in LIVE_REPORT_STATUSES:
        raise GateError(f"live runner {case_id} returned invalid status: {status}")

    report = {
        **payload,
        "schema_version": 1,
        "id": case_id,
        "gate": live_case.get("gate"),
        "commit": git_head(repo_root),
        "authorized": True,
        "authorized_by": effective_authorized_by,
        "authorization_source": "argument" if authorized_by else "environment",
        "created_at": time.time(),
        "side_effects": list(live_case.get("side_effects") or []),
        "config_env": config_env,
    }
    report_path = repo_root / str(live_case.get("report", ""))
    _write_json_atomic(report_path, report)
    return report


def _live_case_for_id(manifest: dict[str, Any], case_id: str) -> dict[str, Any]:
    for live_case in manifest.get("live_cases", []):
        if live_case.get("id") == case_id:
            return live_case
    raise GateError(f"unknown live case: {case_id}")


def _live_runner_not_implemented(
    repo_root: Path,
    live_case: dict[str, Any],
    *,
    config_env: str | None,
    authorized_by: str,
) -> dict[str, Any]:
    raise GateError(
        f"live runner for {live_case.get('id')} is not implemented; "
        "do not mark this live case PASS without a real DSH model run"
    )


@dataclass(frozen=True)
class Live001Workspace:
    work_root: Path
    dsh_home: Path
    data_root: Path
    config_path: Path
    source_data_root: Path


def run_live001_dsh_model_qa(
    repo_root: Path,
    live_case: dict[str, Any],
    *,
    config_env: str | None,
    authorized_by: str,
    source_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    del live_case, config_env, authorized_by
    env_source = dict(os.environ if source_env is None else source_env)
    _require_live001_flash_env(env_source)
    with tempfile.TemporaryDirectory(prefix="paper-rag-live001-") as tmp:
        workspace = _prepare_live001_workspace(repo_root, Path(tmp))
        env = _live001_child_env(repo_root, workspace, env_source)
        summary = _run_live001_headless(repo_root, workspace, env)
        checks = list(summary.get("checks") or [])
        status = "PASS" if checks and all(item.get("status") == "PASS" for item in checks) else "FAIL"
        return {
            "status": status,
            "checks": checks,
            "metrics": summary.get("metrics") or {},
            "model": LIVE001_MODEL,
            "dsh_model": summary.get("dsh_model"),
            "data_root": f"isolated:{workspace.data_root}",
            "source_data_root": _relpath(workspace.source_data_root, repo_root),
            "credential_refs": ["OPENAI_API_KEY"],
            "dsh_credential_ref": "DEEPSEEK_API_KEY",
            "dsh_credential_source_ref": (
                "DEEPSEEK_API_KEY" if env_source.get("DEEPSEEK_API_KEY") else "OPENAI_API_KEY"
            ),
            "side_effect_scope": "temporary isolated data copy and temporary DSH_HOME; cleaned after run",
            "writes_to_formal_paper_library": False,
            "assistant_excerpt": summary.get("assistant_excerpt", ""),
        }


def _require_live001_flash_env(source_env: dict[str, str]) -> None:
    for key in ("CHAT_MODEL", "SMALL_MODEL"):
        if source_env.get(key) != LIVE001_MODEL:
            raise GateError(f"LIVE-001 requires {key}={LIVE001_MODEL}, got {source_env.get(key)!r}")
    if not (source_env.get("OPENAI_API_KEY") or source_env.get("DEEPSEEK_API_KEY")):
        raise GateError("LIVE-001 requires OPENAI_API_KEY or DEEPSEEK_API_KEY")


def _prepare_live001_workspace(repo_root: Path, work_root: Path) -> Live001Workspace:
    source_index = repo_root / "data/index"
    source_sqlite = source_index / "papers.sqlite"
    source_qdrant = source_index / "qdrant_embedded"
    if not source_sqlite.exists():
        raise GateError(f"LIVE-001 source SQLite not found: {_relpath(source_sqlite, repo_root)}")
    if not source_qdrant.exists():
        raise GateError(f"LIVE-001 source Qdrant path not found: {_relpath(source_qdrant, repo_root)}")

    data_root = work_root / "data"
    index_root = data_root / "index"
    dsh_home = work_root / "dsh-home"
    index_root.mkdir(parents=True, exist_ok=True)
    (data_root / "papers").mkdir(parents=True, exist_ok=True)
    (data_root / "parsed").mkdir(parents=True, exist_ok=True)
    (work_root / "artifacts").mkdir(parents=True, exist_ok=True)
    (work_root / "imports").mkdir(parents=True, exist_ok=True)
    (work_root / "credentials").mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_sqlite, index_root / "papers.sqlite")
    source_bm25 = source_index / "bm25.pkl"
    if source_bm25.exists():
        shutil.copy2(source_bm25, index_root / "bm25.pkl")
    shutil.copytree(
        source_qdrant,
        index_root / "qdrant_embedded",
        ignore=shutil.ignore_patterns(".lock"),
        dirs_exist_ok=True,
    )

    preset_source = repo_root / "integrations/deepseek-harness/presets/paper-research"
    preset_dest = dsh_home / ".agent-presets/paper-research"
    if not preset_source.exists():
        raise GateError(f"LIVE-001 preset source not found: {_relpath(preset_source, repo_root)}")
    shutil.copytree(preset_source, preset_dest, dirs_exist_ok=True)

    runner_source = repo_root / "integrations/deepseek-harness/src/paper-rag-headless-runner.mjs"
    runner_dest = dsh_home / "profiles/headless/src/paper-rag-headless-runner.mjs"
    if not runner_source.exists():
        raise GateError(f"LIVE-001 headless runner source not found: {_relpath(runner_source, repo_root)}")
    runner_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(runner_source, runner_dest)

    config_path = work_root / "config.live001.yaml"
    _write_live001_config(repo_root, data_root, index_root, config_path)
    return Live001Workspace(
        work_root=work_root,
        dsh_home=dsh_home,
        data_root=data_root,
        config_path=config_path,
        source_data_root=source_index,
    )


def _write_live001_config(repo_root: Path, data_root: Path, index_root: Path, config_path: Path) -> None:
    source_config = repo_root / "config/local.yaml"
    raw = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    paths = raw.setdefault("paths", {})
    paths.update(
        {
            "data_root": str(data_root),
            "papers_dir": str(data_root / "papers"),
            "parsed_dir": str(data_root / "parsed"),
            "index_dir": str(index_root),
            "sqlite_path": str(index_root / "papers.sqlite"),
            "bm25_path": str(index_root / "bm25.pkl"),
            "models_dir": str(repo_root / "data/index/models"),
        }
    )
    qdrant = raw.setdefault("qdrant", {})
    qdrant.update(
        {
            "url": "",
            "local_path": str(index_root / "qdrant_embedded"),
            "collection_chunks": "paper_chunks",
            "collection_wiki": "wiki_entries",
        }
    )
    raw.setdefault("llm", {})["chat_model"] = "$CHAT_MODEL"
    raw.setdefault("llm", {})["small_model"] = "$SMALL_MODEL"
    config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _live001_child_env(
    repo_root: Path,
    workspace: Live001Workspace,
    source_env: dict[str, str],
) -> dict[str, str]:
    env = dict(source_env)
    if not env.get("DEEPSEEK_API_KEY") and env.get("OPENAI_API_KEY"):
        env["DEEPSEEK_API_KEY"] = env["OPENAI_API_KEY"]
    if not env.get("DEEPSEEK_BASE_URL") and env.get("OPENAI_BASE_URL"):
        env["DEEPSEEK_BASE_URL"] = env["OPENAI_BASE_URL"]
    env.update(
        {
            "CHAT_MODEL": LIVE001_MODEL,
            "SMALL_MODEL": LIVE001_MODEL,
            "DSH_HOME": str(workspace.dsh_home),
            "DSH_TELEMETRY_DISABLED": "1",
            "DSH_TELEMETRY_MODE": "DISABLED",
            "DSH_PERMISSION_MODE": "read-only",
            "DSH_TOOLS_MODE": "native",
            "PAPER_RAG_CONFIG": str(workspace.config_path),
            "PAPER_RAG_REPO_ROOT": str(repo_root),
            "PAPER_RAG_ARTIFACT_ROOT": str(workspace.work_root / "artifacts"),
            "PAPER_RAG_IMPORT_ROOT": str(workspace.work_root / "imports"),
            "PAPER_RAG_MCP_TOOLSET": "readonly",
            "PAPER_RAG_DSH_CREDENTIALS_PATH": str(
                workspace.work_root / "credentials/.credentials.yaml"
            ),
            "PAPER_RAG_DSH_SKILL_ROOT": str(repo_root / ".dsh/skills"),
            "PAPER_RAG_DSH_PRESET_ID": "paper-research",
            "PAPER_RAG_MCP_CREDENTIAL_REFS": json.dumps(["OPENAI_API_KEY"]),
        }
    )
    return env


def _run_live001_headless(
    repo_root: Path,
    workspace: Live001Workspace,
    env: dict[str, str],
) -> dict[str, Any]:
    integration_root = repo_root / "integrations/deepseek-harness"
    dsh_bin = integration_root / "node_modules/.bin/dsh"
    patch_path = integration_root / "live-headless.patch.yml"
    if not dsh_bin.exists():
        raise GateError(f"LIVE-001 DSH binary not found: {_relpath(dsh_bin, repo_root)}")
    if not patch_path.exists():
        raise GateError(f"LIVE-001 headless patch not found: {_relpath(patch_path, repo_root)}")

    proc = subprocess.run(
        [
            str(dsh_bin),
            "--profile",
            "headless",
            "--patch",
            str(patch_path),
            LIVE001_PROMPT,
        ],
        cwd=integration_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=int(env.get("PAPER_RAG_LIVE_TIMEOUT_SEC", "900")),
        check=False,
    )
    try:
        events = _load_dsh_session_events(workspace.dsh_home)
        summary = summarize_live001_events(events, stdout=proc.stdout, stderr=proc.stderr)
    except Exception as exc:  # noqa: BLE001 - live report should record diagnostic failure
        summary = {
            "checks": [
                {
                    "id": "session-events-readable",
                    "status": "FAIL",
                    "detail": str(exc).splitlines()[0][:500],
                }
            ],
            "metrics": {},
            "dsh_model": None,
            "assistant_excerpt": (proc.stdout or proc.stderr)[-500:],
        }
    summary["checks"] = [
        {
            "id": "dsh-headless-exit",
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "detail": f"exit={proc.returncode}",
        },
        *list(summary.get("checks") or []),
    ]
    return summary


def _load_dsh_session_events(dsh_home: Path) -> list[dict[str, Any]]:
    session_paths = sorted(
        (dsh_home / "sessions").rglob("session.jsonl"),
        key=lambda path: path.stat().st_mtime,
    )
    if not session_paths:
        raise GateError(f"no plaintext DSH session log found under {dsh_home / 'sessions'}")
    events: list[dict[str, Any]] = []
    for line in session_paths[-1].read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip():
            events.append(json.loads(line))
    return events


def summarize_live001_events(events: list[dict[str, Any]], *, stdout: str, stderr: str) -> dict[str, Any]:
    tool_calls = [event for event in events if event.get("type") == "tool/call"]
    tool_names = [str((event.get("data") or {}).get("name", "")) for event in tool_calls]
    paper_qa_calls = [event for event in tool_calls if (event.get("data") or {}).get("name") == "paper_qa"]
    text = "\n".join(_event_text(event) for event in events)
    dsh_model = _live001_dsh_model(events)
    citation_ok = _has_nonempty_citation(text)
    abstain_ok = "abstain=no_evidence" in text.lower()
    readonly_names = {
        "paper_status",
        "paper_list",
        "paper_search",
        "paper_qa",
        "paper_section",
        "paper_compare",
        "wiki_lookup",
    }
    disallowed = sorted({name for name in tool_names if name not in readonly_names})
    checks = [
        {
            "id": "dsh-model-flash",
            "status": "PASS" if dsh_model == LIVE001_MODEL else "FAIL",
            "detail": f"model={dsh_model}",
        },
        {
            "id": "readonly-tool-surface",
            "status": "PASS" if tool_calls and not disallowed else "FAIL",
            "detail": f"tool_calls={tool_names} disallowed={disallowed}",
        },
        {
            "id": "paper-qa-called",
            "status": "PASS" if len(paper_qa_calls) >= 2 else "FAIL",
            "detail": f"paper_qa_calls={len(paper_qa_calls)}",
        },
        {
            "id": "fixed-paper-citation",
            "status": "PASS" if citation_ok else "FAIL",
            "detail": LIVE001_POSITIVE_QUESTION,
        },
        {
            "id": "no-evidence-abstain",
            "status": "PASS" if abstain_ok else "FAIL",
            "detail": LIVE001_NEGATIVE_QUESTION,
        },
    ]
    return {
        "checks": checks,
        "metrics": {
            "tool_calls": len(tool_calls),
            "paper_qa_calls": len(paper_qa_calls),
            "citation_checks_passed": 1 if citation_ok else 0,
            "abstain_checks_passed": 1 if abstain_ok else 0,
        },
        "dsh_model": dsh_model,
        "assistant_excerpt": _last_assistant_text(events) or stdout[-500:] or stderr[-500:],
    }


def _event_text(value: Any) -> str:
    if isinstance(value, dict):
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            return value["text"]
        return "\n".join(_event_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_event_text(item) for item in value)
    return ""


def _has_nonempty_citation(text: str) -> bool:
    for token in text.split():
        if token.startswith("citations="):
            return bool(token.removeprefix("citations=").strip().strip(","))
    return False


def _live001_dsh_model(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("type") == "request/header":
            config = (event.get("data") or {}).get("config") or {}
            if config.get("model"):
                return str(config["model"])
    for event in reversed(events):
        if event.get("type") == "assistant/message":
            source = (((event.get("data") or {}).get("message") or {}).get("source") or {})
            if source.get("model"):
                return str(source["model"])
    return None


def _last_assistant_text(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        if event.get("type") == "assistant/message":
            return _event_text((event.get("data") or {}).get("message") or "")[:500]
    return ""


LIVE_CASE_RUNNERS: dict[str, LiveRunner] = {
    "LIVE-001": run_live001_dsh_model_qa,
}


def merge_component_reports(
    repo_root: Path, gate: str, cases: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    component_dir = repo_root / "data" / "index" / "migration-gates" / "components" / gate
    if not component_dir.exists():
        return []

    components: list[dict[str, Any]] = []
    for path in sorted(component_dir.glob("*.json")):
        report = _read_json(path)
        if report.get("gate") != gate:
            raise GateError(
                f"component report gate mismatch for {_relpath(path, repo_root)}: "
                f"expected {gate}, got {report.get('gate')}"
            )
        component = report.get("component") or path.stem
        components.append(
            {
                "component": component,
                "report": _relpath(path, repo_root),
                "go_no_go": report.get("go_no_go"),
            }
        )
        for case_id, case in report.get("cases", {}).items():
            if case_id in cases:
                cases[case_id] = case
    return components


def run_gate(repo_root: Path, manifest_path: Path, gate: str, report_path: Path) -> dict[str, Any]:
    if git_dirty(repo_root):
        raise GateError("run-gate requires clean checkout")
    manifest = _read_json(manifest_path)
    command_by_id = {
        command["id"]: command for command in manifest.get("owned_test_commands", [])
    }
    commands: list[dict[str, Any]] = []
    for command_id in manifest.get("gate_components", {}).get(gate, []):
        command = command_by_id.get(command_id)
        if command is None:
            raise GateError(f"gate {gate} references unknown command: {command_id}")
        cwd = _resolve_command_cwd(repo_root, command.get("repository", "."))
        commands.append(
            {
                "id": command_id,
                "command": command["command"],
                **_run_shell_component(repo_root, command["command"], cwd=cwd),
            }
        )

    required = _required_cases_for_gate(manifest, gate)
    cases = {
        case_id: {
            "status": "NOT_RUN",
            "reason": "case runner not implemented for this compatibility spike",
        }
        for case_id in required
    }
    _inherit_previous_gate_cases(repo_root, manifest, gate, cases)
    components = merge_component_reports(repo_root, gate, cases)
    _apply_command_case_coverage(commands, cases)
    required_pass = all(cases[case_id].get("status") == "PASS" for case_id in required)
    commands_pass = all(command.get("exit_code") == 0 for command in commands)
    result = {
        "schema_version": 1,
        "gate": gate,
        "commit": git_head(repo_root),
        "dirty": git_dirty(repo_root),
        "created_at": time.time(),
        "commands": commands,
        "components": components,
        "cases": cases,
        "go_no_go": "go" if required_pass and commands_pass else "no-go",
    }
    _write_json_atomic(report_path, result)
    return result


def _inherit_previous_gate_cases(
    repo_root: Path,
    manifest: dict[str, Any],
    gate: str,
    cases: dict[str, dict[str, Any]],
) -> None:
    for inherited_gate in manifest.get("inherits_required_cases", {}).get(gate, []):
        report_path = repo_root / "data" / "index" / "migration-gates" / f"{inherited_gate}.json"
        if not report_path.exists():
            continue
        report = _read_json(report_path)
        if report.get("gate") != inherited_gate:
            raise GateError(
                f"inherited report gate mismatch for {_relpath(report_path, repo_root)}"
            )
        for case_id, case in report.get("cases", {}).items():
            if case_id in cases and case.get("status") == "PASS":
                cases[case_id] = {
                    **case,
                    "inherited_from": inherited_gate,
                }


def _apply_command_case_coverage(
    commands: list[dict[str, Any]],
    cases: dict[str, dict[str, Any]],
) -> None:
    for command in commands:
        if command.get("exit_code") != 0:
            continue
        command_id = command.get("id")
        for case_id in CASE_COVERAGE_BY_COMMAND.get(str(command_id), ()):
            if case_id in cases and cases[case_id].get("status") != "PASS":
                cases[case_id] = {
                    "status": "PASS",
                    "evidence": f"command {command_id} passed",
                }


def diff_check(repo_root: Path, base_env: str, head: str) -> dict[str, Any]:
    base = os.environ.get(base_env)
    if not base:
        raise GateError(f"environment variable {base_env} is not set")
    proc = _run_git(repo_root, "diff", "--check", f"{base}...{head}", check=False)
    if proc.returncode != 0:
        raise GateError(proc.stdout.strip() or proc.stderr.strip() or "diff check failed")
    return {"schema_version": 1, "base": base, "head": head}


def extract_make_target_body(makefile_text: str, target: str) -> str:
    lines = makefile_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line == f"{target}:":
            start = i + 1
            break
    if start is None:
        raise GateError(f"Makefile target not found: {target}")

    body: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith(("\t", " ", "#")) and line.endswith(":"):
            break
        body.append(line)
    return "\n".join(body)


def validate_dsh_package(
    package_json: Path,
    *,
    expected_dsh_version: str,
    expected_cordis_version: str,
) -> dict[str, Any]:
    package = _read_json(package_json)
    all_deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = package.get(key, {})
        if isinstance(value, dict):
            all_deps.update(value)

    bad_ranges = {
        name: version
        for name, version in all_deps.items()
        if isinstance(version, str)
        and (version == "latest" or version.startswith(("^", "~", ">", "<", "*")))
    }
    if bad_ranges:
        details = ", ".join(f"{name}={version}" for name, version in sorted(bad_ranges.items()))
        raise GateError(f"non-exact dependency versions: {details}")

    dsh_packages = {
        name: version
        for name, version in all_deps.items()
        if name.startswith("@deepseek-ai/dsh")
    }
    if not dsh_packages:
        raise GateError("no direct @deepseek-ai/dsh* dependencies found")

    wrong_dsh = {
        name: version
        for name, version in dsh_packages.items()
        if version != expected_dsh_version
    }
    if wrong_dsh:
        details = ", ".join(f"{name}={version}" for name, version in sorted(wrong_dsh.items()))
        raise GateError(f"DSH dependency version mismatch: {details}")

    cordis_version = all_deps.get("@deepseek-ai/cordis")
    if cordis_version != expected_cordis_version:
        raise GateError(
            f"@deepseek-ai/cordis must be {expected_cordis_version}, got {cordis_version}"
        )

    return {
        "schema_version": 1,
        "package_json": package_json.as_posix(),
        "dsh_version": expected_dsh_version,
        "cordis_version": expected_cordis_version,
        "dsh_packages": sorted(dsh_packages),
        "pinned": True,
    }


def validate_dsh_lockfile(
    lockfile: Path,
    *,
    expected_dsh_version: str,
    expected_cordis_version: str,
) -> dict[str, Any]:
    try:
        lock = yaml.safe_load(lockfile.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GateError(f"lockfile not found: {lockfile}") from exc
    if not isinstance(lock, dict):
        raise GateError(f"invalid lockfile: {lockfile}")

    package_keys = lock.get("packages", {})
    if not isinstance(package_keys, dict):
        raise GateError("pnpm lockfile missing packages map")

    dsh_versions: set[str] = set()
    cordis_versions: set[str] = set()
    dsh_package_count = 0
    wrong_dsh: list[str] = []
    for key in package_keys:
        parsed = _parse_pnpm_package_key(str(key))
        if parsed is None:
            continue
        name, version = parsed
        if name == "@deepseek-ai/cordis":
            cordis_versions.add(version)
        if name.startswith("@deepseek-ai/dsh"):
            dsh_package_count += 1
            dsh_versions.add(version)
            if version != expected_dsh_version:
                wrong_dsh.append(f"{name}@{version}")

    if cordis_versions != {expected_cordis_version}:
        raise GateError(
            f"expected one Cordis version {expected_cordis_version}, got {sorted(cordis_versions)}"
        )
    if wrong_dsh:
        raise GateError(f"DSH lockfile version mismatch: {', '.join(sorted(wrong_dsh))}")
    if not dsh_package_count:
        raise GateError("no @deepseek-ai/dsh* packages found in lockfile")

    return {
        "schema_version": 1,
        "lockfile": lockfile.as_posix(),
        "cordis_versions": sorted(cordis_versions),
        "dsh_versions": sorted(dsh_versions),
        "dsh_package_count": dsh_package_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("freeze-baseline")
    p.add_argument("--spec", required=True)
    p.add_argument("--out", default="data/index/migration-gates/baseline.json")
    p.add_argument("--allow-dirty", action="store_true")
    p.add_argument("--execute", action="store_true")

    p = sub.add_parser("validate-baseline")
    p.add_argument("--baseline", default="data/index/migration-gates/baseline.json")
    p.add_argument("--spec", default=None)

    p = sub.add_parser("validate-legacy-matrix")
    p.add_argument("--spec", required=True)

    p = sub.add_parser("validate-report")
    p.add_argument("--gate", required=True)
    p.add_argument("--report", required=True)
    p.add_argument(
        "--manifest",
        default="specs/20260813-deepseek-harness-migration/test/test-manifest.json",
    )

    p = sub.add_parser("run-gate")
    p.add_argument("--gate", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--report", required=True)

    p = sub.add_parser("run-live")
    p.add_argument("--case", required=True)
    p.add_argument(
        "--manifest",
        default="specs/20260813-deepseek-harness-migration/test/test-manifest.json",
    )
    p.add_argument("--authorized-by", default=None)
    p.add_argument("--config-env", default=None)

    p = sub.add_parser("validate-live")
    p.add_argument("--gate", required=True)
    p.add_argument(
        "--manifest",
        default="specs/20260813-deepseek-harness-migration/test/test-manifest.json",
    )

    p = sub.add_parser("diff-check")
    p.add_argument("--base-env", required=True)
    p.add_argument("--head", required=True)

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else _discover_repo_root()

    try:
        if args.command == "freeze-baseline":
            result = freeze_baseline(
                repo_root,
                (repo_root / args.spec).resolve(),
                repo_root / args.out,
                require_clean=not args.allow_dirty,
                execute_commands=args.execute,
            )
        elif args.command == "validate-baseline":
            result = validate_baseline(repo_root, repo_root / args.baseline)
        elif args.command == "validate-legacy-matrix":
            spec = repo_root / args.spec
            result = validate_legacy_matrix(repo_root, spec / "legacy-capability-matrix.json")
        elif args.command == "validate-report":
            result = validate_report(
                repo_root, repo_root / args.manifest, args.gate, repo_root / args.report
            )
        elif args.command == "run-gate":
            result = run_gate(repo_root, repo_root / args.manifest, args.gate, repo_root / args.report)
        elif args.command == "run-live":
            result = run_live(
                repo_root,
                repo_root / args.manifest,
                args.case,
                authorized_by=args.authorized_by,
                config_env=args.config_env,
            )
        elif args.command == "validate-live":
            result = validate_live(repo_root, repo_root / args.manifest, args.gate)
        elif args.command == "diff-check":
            result = diff_check(repo_root, args.base_env, args.head)
        else:  # pragma: no cover - argparse enforces command
            raise GateError(f"unknown command: {args.command}")
    except GateError as exc:
        print(f"migration_gate: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _discover_repo_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=True,
    )
    return Path(proc.stdout.strip()).resolve()


def _required_cases_for_gate(manifest: dict[str, Any], gate: str) -> list[str]:
    required: list[str] = []
    for inherited_gate in manifest.get("inherits_required_cases", {}).get(gate, []):
        required.extend(manifest.get("required_cases", {}).get(inherited_gate, []))
    required.extend(manifest.get("required_cases", {}).get(gate, []))
    return list(dict.fromkeys(required))


def _parse_pnpm_package_key(key: str) -> tuple[str, str] | None:
    base = key.split("(", 1)[0]
    if base.startswith("@"):
        idx = base.rfind("@")
        if idx <= 0:
            return None
        return base[:idx], base[idx + 1 :]
    if "@" not in base:
        return None
    name, version = base.rsplit("@", 1)
    return name, version


def _fingerprint(repo_root: Path, rel: Path) -> dict[str, Any]:
    path = repo_root / rel
    if not path.exists():
        raise GateError(f"fingerprint path missing: {rel.as_posix()}")
    data = path.read_bytes()
    return {
        "path": rel.as_posix(),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _resolve_command_cwd(repo_root: Path, repository: str) -> Path:
    candidate = (repo_root / repository).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise GateError(f"command repository escapes repo root: {repository}") from exc
    if not candidate.is_dir():
        raise GateError(f"command repository not found: {repository}")
    return candidate


def _run_shell_component(repo_root: Path, command: str, *, cwd: Path | None = None) -> dict[str, Any]:
    cwd = cwd or repo_root
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "exit_code": proc.returncode,
        "started_at": started,
        "finished_at": time.time(),
        "cwd": _relpath(cwd, repo_root),
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=check,
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GateError(f"json file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GateError(f"invalid json {path}: {exc}") from exc


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _relpath(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
