from __future__ import annotations

import json
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
