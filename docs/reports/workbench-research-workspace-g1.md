# Workbench Research Workspace G1 Report

## Status

Go.

## Implementation Summary

- Added a Workbench-owned local workspace state store backed by SQLite.
- Added project, paper, evidence pin, note, saved question, and project DSH
  handoff APIs.
- Added a Chinese-first Workspace UI, active project switcher, add-to-project
  actions, evidence pinning, project notes, saved QA results, and project DSH
  handoff.
- Kept DSH optional and prompt-only; no DSH private session internals are used.

## Verification

- `.venv/bin/python -m pytest tests/test_workbench_workspace_store.py tests/test_workbench_api.py -q`: PASS, 20 tests.
- `pnpm --dir integrations/paper-rag-workbench test`: PASS, 42 tests.
- `pnpm --dir integrations/paper-rag-workbench build`: PASS.
- `VITE_WORKBENCH_FIXTURES=1 pnpm --dir integrations/paper-rag-workbench playwright`: PASS, 1 test.
- `.venv/bin/python scripts/secret_scan.py`: PASS, clean.
- `git status --short --branch`: clean before this report.

## Degraded Modes

- DSH unavailable does not block Workspace use; project handoff only prepares a
  prompt and URL.
- Workspace state is separate from corpus/index storage, so project actions do
  not ingest, rebuild, reindex, delete, or mutate the real paper library.
- Missing corpus references can still be represented by stored project snapshots.

## Go/No-Go

Go for Gate 2 Compare V1.

## Next Gate

Gate 2 should consume project papers, pinned evidence, notes, and saved
questions to render an evidence-first compare matrix with explicit missing
evidence states.
