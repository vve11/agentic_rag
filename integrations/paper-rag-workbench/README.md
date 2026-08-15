# Paper RAG Workbench

Local visual workbench for the Paper RAG corpus, evidence search, cited QA, and approval-gated discovery ingestion.

## Run

```bash
pnpm --dir integrations/paper-rag-workbench install
.venv/bin/python scripts/start_workbench.py
```

Open `http://127.0.0.1:3090`.

DSH Web remains available at `http://127.0.0.1:3080`.

## Workbench V2

Workbench is the primary Paper RAG research interface. It covers:

- Health: SQLite, Qdrant, retrieval fallback, LLM credential status, and data-quality samples.
- Library: indexed papers with paper detail, sections, chunks, and parser warnings.
- Search: evidence retrieval with inspectable chunk drilldown.
- Ask: streaming generated answers with an agent timeline, citation drilldown, and retrieved evidence.
- Discover: candidate discovery with explicit approval before real-library ingest.
- DSH handoff: copy/open a structured prompt in DSH Web for long-form agent work.

DSH remains the chat and trace companion. Workbench does not depend on DeerFlow
or DSH private session internals.

## Validation

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_workbench_api.py
pnpm --dir integrations/paper-rag-workbench test
pnpm --dir integrations/paper-rag-workbench build
VITE_WORKBENCH_FIXTURES=1 pnpm --dir integrations/paper-rag-workbench playwright
.venv/bin/python scripts/secret_scan.py
```
