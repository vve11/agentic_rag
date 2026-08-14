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
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

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


class GateError(RuntimeError):
    """Raised when migration evidence is missing or invalid."""


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
    components = merge_component_reports(repo_root, gate, cases)
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
