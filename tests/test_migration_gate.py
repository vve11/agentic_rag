from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from scripts import migration_gate

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs" / "20260813-deepseek-harness-migration"


def test_collect_legacy_tests_matches_g0_matrix_scope():
    tests = migration_gate.collect_legacy_tests(ROOT)

    counts = {}
    for item in tests:
        counts[item["file"]] = counts.get(item["file"], 0) + 1

    assert counts == {
        "tests/test_gateway_paper_rag.py": 17,
        "tests/test_middleware.py": 25,
        "tests/test_langgraph_middleware.py": 23,
    }
    assert len(tests) == 65
    assert tests[0]["test_name"].startswith("test_")


def test_validate_legacy_matrix_rejects_missing_test(tmp_path: Path):
    matrix = {
        "schema_version": 1,
        "source_files": ["tests/test_gateway_paper_rag.py"],
        "entries": [
            {
                "file": "tests/test_gateway_paper_rag.py",
                "test_name": "test_routes_registered",
                "classification": "host-specific-delete",
                "replacement": "DSH-G0-003",
                "rationale": "covered by preset composition tests",
            }
        ],
    }
    path = tmp_path / "legacy-capability-matrix.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")

    with pytest.raises(migration_gate.GateError, match="missing 64 legacy tests"):
        migration_gate.validate_legacy_matrix(ROOT, path)


def test_validate_committed_legacy_matrix_covers_all_65_tests():
    result = migration_gate.validate_legacy_matrix(
        ROOT, SPEC / "legacy-capability-matrix.json"
    )

    assert result["total"] == 65
    assert result["by_file"]["tests/test_gateway_paper_rag.py"] == 17
    assert result["by_file"]["tests/test_middleware.py"] == 25
    assert result["by_file"]["tests/test_langgraph_middleware.py"] == 23
    assert set(result["by_classification"]) <= {
        "host-specific-delete",
        "capability-replaced-by-broker-or-mcp",
        "still-required-and-moved",
    }


def test_freeze_baseline_records_dataset_hashes_and_quality_commands(tmp_path: Path):
    out = tmp_path / "baseline.json"
    expected_dirty = migration_gate.git_dirty(ROOT)

    result = migration_gate.freeze_baseline(
        ROOT, SPEC, out, require_clean=False, execute_commands=False
    )

    assert result["schema_version"] == 1
    assert result["commit"]
    assert result["dirty"] == expected_dirty
    paths = {fp["path"] for fp in result["fingerprints"]}
    assert {
        "tests/eval/qa_set.golden.jsonl",
        "tests/eval/gates.strict.json",
        "tests/eval/qa_set.claims.jsonl",
        "tests/eval/gates.claims.json",
        "specs/20260813-deepseek-harness-migration/test/test-manifest.json",
    } <= paths
    commands = {cmd["id"] for cmd in result["commands"]}
    assert {
        "eval-golden",
        "eval-golden-qa",
        "eval-citation-audit",
        "eval-claims",
        "verify-p0",
    } <= commands
    assert json.loads(out.read_text(encoding="utf-8")) == result


def test_validate_baseline_cli_accepts_manifest_spec_argument(tmp_path: Path, capsys):
    baseline = {"fingerprints": []}
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    code = migration_gate.main(
        [
            "--repo-root",
            str(tmp_path),
            "validate-baseline",
            "--spec",
            "specs/20260813-deepseek-harness-migration",
            "--baseline",
            str(baseline_path),
        ]
    )

    assert code == 0
    assert "fingerprints" in capsys.readouterr().out


def test_validate_report_requires_all_g0_cases(tmp_path: Path):
    report = {
        "schema_version": 1,
        "gate": "G0",
        "commit": migration_gate.git_head(ROOT),
        "dirty": False,
        "cases": {"DSH-G0-001": {"status": "PASS"}},
        "commands": [],
        "go_no_go": "no-go",
    }
    path = tmp_path / "G0.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(migration_gate.GateError, match="missing required cases"):
        migration_gate.validate_report(ROOT, SPEC / "test" / "test-manifest.json", "G0", path)


def test_merge_component_reports_updates_required_cases(tmp_path: Path):
    component_dir = tmp_path / "data/index/migration-gates/components/G0"
    component_dir.mkdir(parents=True)
    component = {
        "schema_version": 1,
        "gate": "G0",
        "component": "dsh-g0-compat",
        "cases": {
            "DSH-G0-001": {"status": "PASS", "evidence": "ok"},
            "DSH-G0-002": {"status": "BLOCKED", "reason": "pending"},
            "IGNORED-001": {"status": "PASS", "evidence": "not required"},
        },
        "go_no_go": "no-go",
    }
    (component_dir / "dsh-g0-compat.json").write_text(
        json.dumps(component), encoding="utf-8"
    )
    cases = {
        "DSH-G0-001": {"status": "NOT_RUN"},
        "DSH-G0-002": {"status": "NOT_RUN"},
    }

    components = migration_gate.merge_component_reports(tmp_path, "G0", cases)

    assert components == [
        {
            "component": "dsh-g0-compat",
            "report": "data/index/migration-gates/components/G0/dsh-g0-compat.json",
            "go_no_go": "no-go",
        }
    ]
    assert cases["DSH-G0-001"] == {"status": "PASS", "evidence": "ok"}
    assert cases["DSH-G0-002"] == {"status": "BLOCKED", "reason": "pending"}
    assert "IGNORED-001" not in cases


def test_run_gate_executes_component_in_declared_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo = tmp_path
    component_root = repo / "component"
    component_root.mkdir()
    (component_root / "marker.txt").write_text("ok", encoding="utf-8")
    manifest = {
        "owned_test_commands": [
            {
                "id": "cwd-check",
                "repository": "component",
                "command": (
                    f"{sys.executable} -c "
                    "\"from pathlib import Path; "
                    "print(Path.cwd().name); "
                    "assert Path('marker.txt').read_text() == 'ok'\""
                ),
            }
        ],
        "gate_components": {"G0": ["cwd-check"]},
        "required_cases": {"G0": []},
    }
    manifest_path = repo / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report_path = repo / "G0.json"
    monkeypatch.setattr(migration_gate, "git_dirty", lambda _repo_root: False)
    monkeypatch.setattr(migration_gate, "git_head", lambda _repo_root: "test-head")

    report = migration_gate.run_gate(repo, manifest_path, "G0", report_path)

    command = report["commands"][0]
    assert command["status"] == "PASS"
    assert command["cwd"] == "component"
    assert command["stdout"].strip() == "component"


def test_run_gate_inherits_previous_gate_cases_and_marks_command_covered_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    report_root = tmp_path / "data/index/migration-gates"
    report_root.mkdir(parents=True)
    (report_root / "G0.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "gate": "G0",
                "commit": "previous-head",
                "dirty": False,
                "cases": {"DSH-G0-001": {"status": "PASS", "evidence": "locked"}},
                "commands": [],
                "go_no_go": "go",
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "owned_test_commands": [
            {
                "id": "mcp-contract",
                "repository": ".",
                "command": f"{sys.executable} -c \"print('contract ok')\"",
            }
        ],
        "gate_components": {"G1": ["mcp-contract"]},
        "required_cases": {
            "G0": ["DSH-G0-001"],
            "G1": ["MCP-001", "MCP-002", "MCP-003", "MCP-004", "MCP-005", "MCP-006", "MCP-007"],
        },
        "inherits_required_cases": {"G1": ["G0"]},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report_path = report_root / "G1.json"
    monkeypatch.setattr(migration_gate, "git_dirty", lambda _repo_root: False)
    monkeypatch.setattr(migration_gate, "git_head", lambda _repo_root: "test-head")

    report = migration_gate.run_gate(tmp_path, manifest_path, "G1", report_path)

    assert report["cases"]["DSH-G0-001"]["status"] == "PASS"
    assert report["cases"]["MCP-001"]["status"] == "PASS"
    assert report["cases"]["MCP-007"]["evidence"] == "command mcp-contract passed"
    assert report["go_no_go"] == "go"


def test_validate_live_requires_authorized_fresh_pass_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report_path = tmp_path / "data/index/migration-gates/live/LIVE-001.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "LIVE-001",
                "gate": "G1",
                "commit": "test-head",
                "status": "PASS",
                "authorized": True,
                "created_at": time.time(),
                "side_effects": ["real LLM calls"],
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "live_cases": [
            {
                "id": "LIVE-001",
                "gate": "G1",
                "report": "data/index/migration-gates/live/LIVE-001.json",
                "max_age_hours": 24,
                "requires_authorization": True,
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(migration_gate, "git_head", lambda _repo_root: "test-head")

    result = migration_gate.validate_live(tmp_path, manifest_path, "G1")

    assert result["gate"] == "G1"
    assert result["live_cases"] == ["LIVE-001"]


def test_validate_live_rejects_missing_or_unauthorized_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = {
        "live_cases": [
            {
                "id": "LIVE-001",
                "gate": "G1",
                "report": "data/index/migration-gates/live/LIVE-001.json",
                "max_age_hours": 24,
                "requires_authorization": True,
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(migration_gate.GateError, match="live report not found"):
        migration_gate.validate_live(tmp_path, manifest_path, "G1")

    report_path = tmp_path / "data/index/migration-gates/live/LIVE-001.json"
    report_path.parent.mkdir(parents=True)
    monkeypatch.setattr(migration_gate, "git_head", lambda _repo_root: "test-head")
    report_path.write_text(
        json.dumps(
            {
                "id": "LIVE-001",
                "gate": "G1",
                "commit": "test-head",
                "status": "PASS",
                "authorized": False,
                "created_at": time.time(),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(migration_gate.GateError, match="not authorized"):
        migration_gate.validate_live(tmp_path, manifest_path, "G1")


def test_run_live_requires_explicit_authorization_before_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = {
        "live_cases": [
            {
                "id": "LIVE-001",
                "gate": "G1",
                "report": "data/index/migration-gates/live/LIVE-001.json",
                "requires_authorization": True,
                "side_effects": ["real LLM calls"],
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(migration_gate, "git_dirty", lambda _repo_root: False)
    called = {"runner": False}

    def fake_runner(*args, **kwargs):
        called["runner"] = True
        return {"status": "PASS"}

    with pytest.raises(migration_gate.GateError, match="requires explicit authorization"):
        migration_gate.run_live(
            tmp_path,
            manifest_path,
            "LIVE-001",
            runner_registry={"LIVE-001": fake_runner},
        )

    assert called["runner"] is False
    assert not (tmp_path / "data/index/migration-gates/live/LIVE-001.json").exists()


def test_run_live_writes_authorized_current_commit_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = {
        "live_cases": [
            {
                "id": "LIVE-001",
                "gate": "G1",
                "report": "data/index/migration-gates/live/LIVE-001.json",
                "max_age_hours": 24,
                "requires_authorization": True,
                "side_effects": ["real LLM calls"],
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(migration_gate, "git_dirty", lambda _repo_root: False)
    monkeypatch.setattr(migration_gate, "git_head", lambda _repo_root: "test-head")

    def fake_runner(repo_root, live_case, *, config_env, authorized_by):
        return {
            "status": "PASS",
            "checks": [{"id": "fixed-paper-qa", "status": "PASS"}],
            "metrics": {"cite_precision": 1.0, "abstain_ok": 1.0},
            "data_root": "data/index",
            "credential_refs": ["OPENAI_API_KEY"],
            "model": "deepseek-v4-flash",
        }

    result = migration_gate.run_live(
        tmp_path,
        manifest_path,
        "LIVE-001",
        authorized_by="at",
        config_env="PAPER_RAG_CONFIG",
        runner_registry={"LIVE-001": fake_runner},
    )

    assert result["id"] == "LIVE-001"
    assert result["gate"] == "G1"
    assert result["status"] == "PASS"
    assert result["authorized"] is True
    assert result["authorized_by"] == "at"
    assert result["commit"] == "test-head"
    assert result["side_effects"] == ["real LLM calls"]
    assert result["config_env"] == "PAPER_RAG_CONFIG"
    assert result["checks"] == [{"id": "fixed-paper-qa", "status": "PASS"}]
    assert json.loads((tmp_path / "data/index/migration-gates/live/LIVE-001.json").read_text()) == result
    assert migration_gate.validate_live(tmp_path, manifest_path, "G1")["live_cases"] == ["LIVE-001"]


def test_live001_runner_uses_isolated_workspace_and_flash_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source_env = {
        "OPENAI_API_KEY": "test-secret",
        "OPENAI_BASE_URL": "https://api.deepseek.com",
        "CHAT_MODEL": "deepseek-v4-flash",
        "SMALL_MODEL": "deepseek-v4-flash",
    }
    workspace = migration_gate.Live001Workspace(
        work_root=tmp_path / "work",
        dsh_home=tmp_path / "work/dsh-home",
        data_root=tmp_path / "work/data",
        config_path=tmp_path / "work/config.yaml",
        source_data_root=tmp_path / "data/index",
    )
    captured = {}

    monkeypatch.setattr(
        migration_gate,
        "_prepare_live001_workspace",
        lambda repo_root, work_root: workspace,
    )

    def fake_headless(repo_root, prepared, env):
        captured["repo_root"] = repo_root
        captured["workspace"] = prepared
        captured["env"] = env
        return {
            "checks": [
                {"id": "dsh-headless-exit", "status": "PASS"},
                {"id": "fixed-paper-citation", "status": "PASS"},
                {"id": "no-evidence-abstain", "status": "PASS"},
            ],
            "metrics": {
                "tool_calls": 2,
                "paper_qa_calls": 2,
                "citation_checks_passed": 1,
                "abstain_checks_passed": 1,
            },
            "dsh_model": "deepseek-v4-flash",
            "assistant_excerpt": "ok",
        }

    monkeypatch.setattr(migration_gate, "_run_live001_headless", fake_headless)

    result = migration_gate.run_live001_dsh_model_qa(
        tmp_path,
        {"id": "LIVE-001"},
        config_env=None,
        authorized_by="at",
        source_env=source_env,
    )

    assert result["status"] == "PASS"
    assert result["model"] == "deepseek-v4-flash"
    assert result["dsh_model"] == "deepseek-v4-flash"
    assert result["data_root"].startswith("isolated:")
    assert result["source_data_root"] == "data/index"
    assert result["credential_refs"] == ["OPENAI_API_KEY"]
    assert "test-secret" not in json.dumps(result)
    assert captured["env"]["CHAT_MODEL"] == "deepseek-v4-flash"
    assert captured["env"]["SMALL_MODEL"] == "deepseek-v4-flash"
    assert captured["env"]["DEEPSEEK_API_KEY"] == "test-secret"
    assert captured["env"]["PAPER_RAG_CONFIG"] == str(workspace.config_path)
    assert captured["env"]["DSH_HOME"] == str(workspace.dsh_home)
    assert captured["env"]["PAPER_RAG_MCP_TOOLSET"] == "readonly"


def test_live001_summary_requires_paper_qa_citation_and_abstain():
    events = [
        {
            "type": "request/header",
            "data": {"config": {"provider": "deepseek-official", "model": "deepseek-v4-flash"}},
        },
        {
            "type": "tool/call",
            "data": {
                "name": "paper_qa",
                "arguments": json.dumps(
                    {"question": migration_gate.LIVE001_POSITIVE_QUESTION}
                ),
            },
        },
        {
            "type": "tool/result",
            "data": {
                "message": {
                    "content": [
                        {
                            "type": "tool-result",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "ok=true tool=paper_qa citations=563088608864d1932716",
                                }
                            ],
                        }
                    ]
                }
            },
        },
        {
            "type": "tool/call",
            "data": {
                "name": "paper_qa",
                "arguments": json.dumps(
                    {"question": migration_gate.LIVE001_NEGATIVE_QUESTION}
                ),
            },
        },
        {
            "type": "tool/result",
            "data": {
                "message": {
                    "content": [
                        {
                            "type": "tool-result",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "ok=true tool=paper_qa abstain=no_evidence citations=",
                                }
                            ],
                        }
                    ]
                }
            },
        },
        {
            "type": "assistant/message",
            "data": {
                "message": {
                    "content": [{"type": "text", "text": "LIVE-001 complete"}],
                    "source": {"provider": "deepseek-official", "model": "deepseek-v4-flash"},
                }
            },
        },
    ]

    summary = migration_gate.summarize_live001_events(events, stdout="", stderr="")

    assert summary["dsh_model"] == "deepseek-v4-flash"
    assert summary["metrics"] == {
        "tool_calls": 2,
        "paper_qa_calls": 2,
        "citation_checks_passed": 1,
        "abstain_checks_passed": 1,
    }
    assert all(check["status"] == "PASS" for check in summary["checks"])

    broken = [
        event
        for event in events
        if event.get("type") != "tool/result"
        or "abstain=no_evidence" not in json.dumps(event)
    ]
    broken_summary = migration_gate.summarize_live001_events(broken, stdout="", stderr="")

    assert broken_summary["metrics"]["abstain_checks_passed"] == 0
    assert any(
        check["id"] == "no-evidence-abstain" and check["status"] == "FAIL"
        for check in broken_summary["checks"]
    )


def test_quality_gate_make_targets_use_migration_python():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    for target in [
        "eval-golden",
        "eval-golden-qa",
        "eval-citation-audit",
        "eval-claims",
        "eval-claims-report",
        "eval-claims-judge",
        "eval-llm-recall",
        "verify-p0",
    ]:
        body = migration_gate.extract_make_target_body(makefile, target)
        assert "DEERFLOW_BACKEND_PY" not in body
        assert "$(PY)" in body


def test_g0_manifest_citation_audit_writes_to_gate_artifact_dir():
    manifest = json.loads((SPEC / "test" / "test-manifest.json").read_text(encoding="utf-8"))
    command_by_id = {command["id"]: command["command"] for command in manifest["owned_test_commands"]}

    command = command_by_id["eval-citation-audit"]

    assert "EVAL_CITATION_AUDIT_MD=data/index/migration-gates/" in command
    assert "docs/RAG_CITATION_AUDIT.md" not in command


def test_dsh_package_uses_exact_compatible_versions():
    result = migration_gate.validate_dsh_package(
        ROOT / "integrations" / "deepseek-harness" / "package.json",
        expected_dsh_version="0.1.0-rc.6",
        expected_cordis_version="4.0.1",
    )

    assert result["dsh_version"] == "0.1.0-rc.6"
    assert result["cordis_version"] == "4.0.1"
    assert "@deepseek-ai/dsh-tool-call-timeout-policy" in result["dsh_packages"]
    assert result["pinned"] is True


def test_dsh_lockfile_resolves_single_cordis_and_dsh_version():
    result = migration_gate.validate_dsh_lockfile(
        ROOT / "integrations" / "deepseek-harness" / "pnpm-lock.yaml",
        expected_dsh_version="0.1.0-rc.6",
        expected_cordis_version="4.0.1",
    )

    assert result["cordis_versions"] == ["4.0.1"]
    assert result["dsh_versions"] == ["0.1.0-rc.6"]
    assert result["dsh_package_count"] >= 100
