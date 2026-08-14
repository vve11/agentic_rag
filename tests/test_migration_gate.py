from __future__ import annotations

import json
import sys
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

    result = migration_gate.freeze_baseline(
        ROOT, SPEC, out, require_clean=False, execute_commands=False
    )

    assert result["schema_version"] == 1
    assert result["commit"]
    assert result["dirty"] is True
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
