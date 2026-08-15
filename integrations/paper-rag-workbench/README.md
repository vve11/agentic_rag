# Paper RAG Workbench

Local visual workbench for the Paper RAG corpus, evidence search, cited QA, and approval-gated discovery ingestion.

## Run

```bash
pnpm --dir integrations/paper-rag-workbench install
.venv/bin/python scripts/start_workbench.py
```

Open `http://127.0.0.1:3090`.

DSH Web remains available at `http://127.0.0.1:3080`.

## Validation

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_workbench_api.py
pnpm --dir integrations/paper-rag-workbench test
pnpm --dir integrations/paper-rag-workbench build
VITE_WORKBENCH_FIXTURES=1 pnpm --dir integrations/paper-rag-workbench playwright
.venv/bin/python scripts/secret_scan.py
```
