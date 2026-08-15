# Paper RAG Workbench V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Paper RAG Workbench V2 as the primary local research workbench with index health, paper detail, citation drilldown, and DSH handoff.

**Architecture:** Extend the existing FastAPI Workbench adapter and React SPA. Keep Paper RAG business logic in `src/paper_rag`, use MCP tools for existing research operations, and add small read-only Workbench helpers only for diagnostics/detail views that are not model-facing tools.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLModel, React 18, TypeScript, Vite, Vitest, Testing Library, Playwright fixture smoke.

## Global Constraints

- Keep `deepseek-v4-flash` as the configured model.
- Do not restore or create `integrations/deer-flow/`.
- Do not commit `.env`, API keys, `data/index`, runtime credentials, DSH sessions, real PDFs, generated `dist`, `node_modules`, or temporary smoke data.
- Do not execute real-library write smoke tests unless the user explicitly approves that run.
- Preserve explicit approval for every real write path.
- Workbench remains independent. DSH Web remains the separate trace/chat companion at the configured `dsh_url`.
- Add dependencies only when they remove clear complexity; this plan needs no new runtime dependencies.

---

## File Structure

- Create `src/paper_rag/workbench/read_store.py`
  - Owns read-only SQLite access for Workbench-only views.
  - Validates path ids, redacts unsafe fields, detects parser warnings, and returns paper/chunk detail dictionaries.
- Create `src/paper_rag/workbench/diagnostics.py`
  - Builds `/api/health/index` from the read store, config, Qdrant probe, LLM settings, and credential status.
  - Never returns raw secrets or absolute local artifact/PDF paths.
- Modify `src/paper_rag/workbench/api.py`
  - Adds injectable read-only helpers for tests.
  - Adds `GET /api/health/index`, `GET /api/papers/{paper_id:path}`, `GET /api/chunks/{chunk_id}`, and `POST /api/dsh/handoff`.
- Modify `src/paper_rag/workbench/schemas.py`
  - Adds strict request schemas for DSH handoff.
- Add tests to `tests/test_workbench_read_store.py`
  - Covers detail dictionaries, warning detection, bounded id validation, and path redaction.
- Extend `tests/test_workbench_api.py`
  - Covers new endpoints, secret safety, no write calls, and handoff prompt construction.
- Modify `integrations/paper-rag-workbench/src/types.ts`
  - Adds typed contracts for health, detail, chunk drilldown, score breakdown, and DSH handoff.
- Modify `integrations/paper-rag-workbench/src/api/client.ts`
  - Adds client methods for new endpoints and fixture-mode responses.
- Modify `integrations/paper-rag-workbench/src/api/fixtures.ts`
  - Adds degraded-health, paper-detail, chunk-detail, and handoff fixtures.
- Create frontend components:
  - `integrations/paper-rag-workbench/src/components/WarningBanner.tsx`
  - `integrations/paper-rag-workbench/src/components/DiagnosticCard.tsx`
  - `integrations/paper-rag-workbench/src/components/HealthSummary.tsx`
  - `integrations/paper-rag-workbench/src/components/QualityIssueTable.tsx`
  - `integrations/paper-rag-workbench/src/components/PaperDetailPanel.tsx`
  - `integrations/paper-rag-workbench/src/components/ChunkDetailPanel.tsx`
  - `integrations/paper-rag-workbench/src/components/ScoreBreakdown.tsx`
  - `integrations/paper-rag-workbench/src/components/DshHandoffDialog.tsx`
- Create frontend pages:
  - `integrations/paper-rag-workbench/src/pages/HealthPage.tsx`
- Modify existing frontend files:
  - `integrations/paper-rag-workbench/src/App.tsx`
  - `integrations/paper-rag-workbench/src/components/Shell.tsx`
  - `integrations/paper-rag-workbench/src/components/EvidenceChunkCard.tsx`
  - `integrations/paper-rag-workbench/src/components/CitationChips.tsx`
  - `integrations/paper-rag-workbench/src/components/AnswerPanel.tsx`
  - `integrations/paper-rag-workbench/src/pages/AskPage.tsx`
  - `integrations/paper-rag-workbench/src/pages/SearchPage.tsx`
  - `integrations/paper-rag-workbench/src/pages/LibraryPage.tsx`
  - `integrations/paper-rag-workbench/src/pages/OverviewPage.tsx`
  - `integrations/paper-rag-workbench/src/styles.css`
- Extend frontend tests:
  - `integrations/paper-rag-workbench/src/__tests__/client.test.ts`
  - `integrations/paper-rag-workbench/src/__tests__/components.test.tsx`
  - `integrations/paper-rag-workbench/src/__tests__/pages.test.tsx`
- Extend Playwright fixture smoke:
  - Extend `integrations/paper-rag-workbench/tests/workbench.spec.ts`.
- Update docs:
  - `integrations/paper-rag-workbench/README.md`
  - `README.md`

---

### Task 1: Read-Only Workbench Store

**Files:**
- Create: `src/paper_rag/workbench/read_store.py`
- Create: `tests/test_workbench_read_store.py`

**Interfaces:**
- Produces: `validate_bounded_id(value: str, field_name: str, *, max_length: int = 180) -> str`
- Produces: `parser_warnings_for_text(text: str) -> list[str]`
- Produces: `redact_local_path(value: str | None) -> str | None`
- Produces: `class WorkbenchReadStore`
- Produces: `WorkbenchReadStore.paper_detail(paper_id: str) -> dict[str, Any] | None`
- Produces: `WorkbenchReadStore.chunk_detail(chunk_id: str, *, neighbor_limit: int = 2) -> dict[str, Any] | None`
- Produces: `WorkbenchReadStore.corpus_quality(limit: int = 8) -> dict[str, Any]`
- Consumes: `Paper`, `Section`, `Chunk`, and `get_engine` from `src/paper_rag/store/sqlite_store.py`

- [ ] **Step 1: Write the failing read-store tests**

Add this file:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from paper_rag.store.sqlite_store import Chunk, Paper, Section


def _engine(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'paper-rag.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _seed(engine) -> None:
    with Session(engine) as session:
        session.add(
            Paper(
                paper_id="arxiv:2310.11511",
                title="Self-RAG",
                arxiv_id="2310.11511",
                year=2023,
                abstract="Self-RAG abstract.",
                status="done",
                parsed_with="pymupdf",
            )
        )
        session.add(
            Section(
                section_id="sec-intro",
                paper_id="arxiv:2310.11511",
                idx=1,
                name="Introduction",
                page_start=1,
                page_end=2,
            )
        )
        session.add(
            Chunk(
                chunk_id="chunk-a",
                paper_id="arxiv:2310.11511",
                section_id="sec-intro",
                section="Introduction",
                section_idx=1,
                page=1,
                title="Self-RAG",
                text="SELF-RAG retrieves passages on demand.",
                context_text="SELF-RAG retrieves passages on demand.",
                source_path="/Users/at/private/papers/self-rag.pdf",
                asset_path="/Users/at/private/assets/page-1.png",
            )
        )
        session.add(
            Chunk(
                chunk_id="chunk-b",
                paper_id="arxiv:2310.11511",
                section_id="sec-intro",
                section="Introduction",
                section_idx=1,
                page=2,
                title="Self-RAG",
                text="<!-- page 2 --> SELF-RAG retrieves passages on demand. Preprint.",
                context_text="<!-- page 2 --> SELF-RAG retrieves passages on demand. Preprint.",
            )
        )
        session.commit()


def test_paper_detail_returns_sections_chunks_and_redacts_paths(tmp_path):
    from paper_rag.workbench.read_store import WorkbenchReadStore

    engine = _engine(tmp_path)
    _seed(engine)

    detail = WorkbenchReadStore(engine=engine).paper_detail("arxiv:2310.11511")

    assert detail is not None
    assert detail["paper"]["paper_id"] == "arxiv:2310.11511"
    assert detail["paper"]["title"] == "Self-RAG"
    assert detail["sections"] == [
        {
            "section_id": "sec-intro",
            "name": "Introduction",
            "idx": 1,
            "page_start": 1,
            "page_end": 2,
            "chunk_count": 2,
        }
    ]
    assert detail["chunks"][0]["chunk_id"] == "chunk-a"
    assert "source_path" not in str(detail)
    assert "asset_path" not in str(detail)
    assert "/Users/at/private" not in str(detail)


def test_chunk_detail_returns_neighbors_and_parser_warnings(tmp_path):
    from paper_rag.workbench.read_store import WorkbenchReadStore

    engine = _engine(tmp_path)
    _seed(engine)

    detail = WorkbenchReadStore(engine=engine).chunk_detail("chunk-b")

    assert detail is not None
    assert detail["chunk"]["chunk_id"] == "chunk-b"
    assert "html_comment" in detail["chunk"]["warnings"]
    assert "preprint_marker" in detail["chunk"]["warnings"]
    assert [chunk["chunk_id"] for chunk in detail["neighbors"]] == ["chunk-a"]


def test_corpus_quality_detects_duplicate_text_and_parser_artifacts(tmp_path):
    from paper_rag.workbench.read_store import WorkbenchReadStore

    engine = _engine(tmp_path)
    _seed(engine)

    quality = WorkbenchReadStore(engine=engine).corpus_quality()

    assert quality["paper_count"] == 1
    assert quality["chunk_count"] == 2
    assert quality["duplicate_chunk_count"] == 1
    assert quality["parser_artifact_count"] == 1
    assert quality["samples"][0]["kind"] in {"duplicate_chunk", "parser_artifact"}


@pytest.mark.parametrize("value", ["", "x" * 181, "../paper", "paper\nid"])
def test_validate_bounded_id_rejects_unsafe_values(value):
    from paper_rag.workbench.read_store import validate_bounded_id

    with pytest.raises(ValueError):
        validate_bounded_id(value, "paper_id")
```

- [ ] **Step 2: Run the read-store tests to verify they fail**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_workbench_read_store.py
```

Expected: failure because `paper_rag.workbench.read_store` does not exist.

- [ ] **Step 3: Implement `src/paper_rag/workbench/read_store.py`**

Use this structure:

```python
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from paper_rag.store.sqlite_store import Chunk, Paper, Section, get_engine

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SPACE_RE = re.compile(r"\s+")


def validate_bounded_id(value: str, field_name: str, *, max_length: int = 180) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        raise ValueError(f"{field_name} is required")
    if len(candidate) > max_length:
        raise ValueError(f"{field_name} is too long")
    if any(token in candidate for token in ("..", "/", "\\", "\n", "\r", "\x00")):
        raise ValueError(f"{field_name} contains unsupported characters")
    return candidate


def redact_local_path(value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    if path.name:
        return f"[redacted]/{path.name}"
    return "[redacted]"


def parser_warnings_for_text(text: str) -> list[str]:
    warnings: list[str] = []
    if _HTML_COMMENT_RE.search(text):
        warnings.append("html_comment")
    if "Preprint." in text:
        warnings.append("preprint_marker")
    return warnings


def _normalized_text(text: str) -> str:
    without_comments = _HTML_COMMENT_RE.sub(" ", text or "")
    without_preprint = without_comments.replace("Preprint.", " ")
    return _SPACE_RE.sub(" ", without_preprint).strip().lower()


def _chunk_summary(chunk: Chunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "paper_id": chunk.paper_id,
        "title": chunk.title,
        "section_id": chunk.section_id,
        "section": chunk.section,
        "section_idx": chunk.section_idx,
        "page": chunk.page,
        "modality": chunk.modality,
        "text": chunk.text,
        "snippet": (chunk.text or chunk.context_text or "")[:500],
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "warnings": parser_warnings_for_text(chunk.text or chunk.context_text or ""),
    }


class WorkbenchReadStore:
    def __init__(self, *, engine: Any | None = None) -> None:
        self._engine = engine

    @property
    def engine(self):
        return self._engine or get_engine()

    def paper_detail(self, paper_id: str) -> dict[str, Any] | None:
        safe_id = validate_bounded_id(paper_id, "paper_id")
        with Session(self.engine) as session:
            paper = session.get(Paper, safe_id)
            if paper is None:
                return None
            sections = list(
                session.exec(
                    select(Section)
                    .where(Section.paper_id == safe_id)
                    .order_by(Section.idx)
                )
            )
            chunks = list(
                session.exec(
                    select(Chunk)
                    .where(Chunk.paper_id == safe_id)
                    .order_by(Chunk.section_idx, Chunk.page, Chunk.chunk_id)
                )
            )

        counts = Counter(chunk.section_id for chunk in chunks)
        return {
            "paper": {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "arxiv_id": paper.arxiv_id,
                "year": paper.year,
                "venue": paper.venue,
                "doi": paper.doi,
                "abstract": paper.abstract,
                "status": paper.status,
                "parsed_with": paper.parsed_with,
                "chunk_count": len(chunks),
                "updated_at": paper.updated_at.isoformat(),
            },
            "sections": [
                {
                    "section_id": section.section_id,
                    "name": section.name,
                    "idx": section.idx,
                    "page_start": section.page_start,
                    "page_end": section.page_end,
                    "chunk_count": counts.get(section.section_id, 0),
                }
                for section in sections
            ],
            "chunks": [_chunk_summary(chunk) for chunk in chunks],
            "warnings": _paper_warnings(sections, chunks),
        }

    def chunk_detail(self, chunk_id: str, *, neighbor_limit: int = 2) -> dict[str, Any] | None:
        safe_id = validate_bounded_id(chunk_id, "chunk_id")
        with Session(self.engine) as session:
            chunk = session.get(Chunk, safe_id)
            if chunk is None:
                return None
            paper = session.get(Paper, chunk.paper_id)
            peers = list(
                session.exec(
                    select(Chunk)
                    .where(Chunk.paper_id == chunk.paper_id)
                    .order_by(Chunk.section_idx, Chunk.page, Chunk.chunk_id)
                )
            )

        index = next((idx for idx, peer in enumerate(peers) if peer.chunk_id == safe_id), -1)
        start = max(0, index - neighbor_limit)
        end = min(len(peers), index + neighbor_limit + 1)
        neighbors = [peer for peer in peers[start:end] if peer.chunk_id != safe_id]
        return {
            "chunk": _chunk_summary(chunk),
            "paper": {
                "paper_id": paper.paper_id if paper else chunk.paper_id,
                "title": paper.title if paper else chunk.title,
                "arxiv_id": paper.arxiv_id if paper else None,
                "year": paper.year if paper else None,
            },
            "neighbors": [_chunk_summary(peer) for peer in neighbors],
        }

    def corpus_quality(self, limit: int = 8) -> dict[str, Any]:
        with Session(self.engine) as session:
            papers = list(session.exec(select(Paper)))
            chunks = list(session.exec(select(Chunk)))

        normalized_to_chunks: dict[str, list[Chunk]] = defaultdict(list)
        parser_samples: list[dict[str, Any]] = []
        parser_artifact_count = 0
        for chunk in chunks:
            normalized = _normalized_text(chunk.text or chunk.context_text or "")
            if normalized:
                normalized_to_chunks[normalized].append(chunk)
            warnings = parser_warnings_for_text(chunk.text or chunk.context_text or "")
            if warnings:
                parser_artifact_count += 1
                if len(parser_samples) < limit:
                    parser_samples.append(
                        {
                            "kind": "parser_artifact",
                            "paper_id": chunk.paper_id,
                            "chunk_id": chunk.chunk_id,
                            "warnings": warnings,
                            "preview": (chunk.text or chunk.context_text or "")[:180],
                        }
                    )

        duplicate_groups = [items for items in normalized_to_chunks.values() if len(items) > 1]
        duplicate_samples = [
            {
                "kind": "duplicate_chunk",
                "paper_id": group[0].paper_id,
                "chunk_ids": [chunk.chunk_id for chunk in group[:4]],
                "preview": (group[0].text or group[0].context_text or "")[:180],
            }
            for group in duplicate_groups[:limit]
        ]
        missing_section_count = sum(
            1
            for paper in papers
            if not any(
                chunk.paper_id == paper.paper_id
                and (chunk.section or "").strip().lower() in {"abstract", "introduction"}
                for chunk in chunks
            )
        )
        return {
            "paper_count": len(papers),
            "chunk_count": len(chunks),
            "duplicate_chunk_count": sum(len(group) - 1 for group in duplicate_groups),
            "parser_artifact_count": parser_artifact_count,
            "missing_section_count": missing_section_count,
            "samples": (duplicate_samples + parser_samples)[:limit],
        }


def _paper_warnings(sections: list[Section], chunks: list[Chunk]) -> list[str]:
    warnings: list[str] = []
    if not sections:
        warnings.append("section_metadata_missing")
    if not any((chunk.section or "").strip().lower() == "abstract" for chunk in chunks):
        warnings.append("abstract_section_missing")
    if not any((chunk.section or "").strip().lower() == "introduction" for chunk in chunks):
        warnings.append("introduction_section_missing")
    if any(parser_warnings_for_text(chunk.text or chunk.context_text or "") for chunk in chunks):
        warnings.append("parser_artifacts_detected")
    return warnings
```

- [ ] **Step 4: Run the read-store tests to verify they pass**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_workbench_read_store.py
```

Expected: all tests in `tests/test_workbench_read_store.py` pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/paper_rag/workbench/read_store.py tests/test_workbench_read_store.py
git commit -m "feat: add workbench read store"
```

---

### Task 2: Backend V2 Endpoints

**Files:**
- Create: `src/paper_rag/workbench/diagnostics.py`
- Modify: `src/paper_rag/workbench/api.py`
- Modify: `src/paper_rag/workbench/schemas.py`
- Modify: `tests/test_workbench_api.py`

**Interfaces:**
- Consumes: `WorkbenchReadStore` from Task 1.
- Produces: `build_index_health(settings: WorkbenchSettings, *, read_store: WorkbenchReadStore | None = None) -> dict[str, Any]`
- Produces: `DshHandoffRequest` in `schemas.py`
- Produces: `GET /api/health/index`
- Produces: `GET /api/papers/{paper_id:path}`
- Produces: `GET /api/chunks/{chunk_id}`
- Produces: `POST /api/dsh/handoff`

- [ ] **Step 1: Write failing API tests**

Append these tests to `tests/test_workbench_api.py`:

```python
def test_index_health_endpoint_uses_read_only_builder(tmp_path):
    from paper_rag.workbench.api import create_app

    def fake_index_health(settings):
        assert settings.chat_model == "deepseek-v4-flash"
        return {
            "status": "degraded",
            "sqlite": {
                "available": True,
                "paper_count": 8,
                "chunk_count": 345,
                "fts_available": True,
            },
            "qdrant": {
                "configured": True,
                "mode": "server",
                "reachable": False,
                "degraded_reason": "connection refused",
            },
            "retrieval": {
                "dense_available": False,
                "sparse_available": True,
                "hybrid_available": True,
            },
            "llm": {
                "configured": True,
                "chat_model": "deepseek-v4-flash",
                "base_url_host": "api.deepseek.com",
                "credential_source": "file",
            },
            "corpus_quality": {
                "duplicate_chunk_count": 1,
                "parser_artifact_count": 1,
                "missing_section_count": 0,
                "samples": [],
            },
            "warnings": ["Dense retrieval is unavailable; sparse fallback is active."],
        }

    client = TestClient(
        create_app(
            _settings(tmp_path),
            call_tool_fn=lambda *_args: {},
            index_health_fn=fake_index_health,
        )
    )

    response = client.get("/api/health/index")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["llm"]["chat_model"] == "deepseek-v4-flash"
    assert "sk-" not in str(payload)


def test_paper_detail_endpoint_returns_404_for_missing_paper(tmp_path):
    from paper_rag.workbench.api import create_app

    class FakeReadStore:
        def paper_detail(self, paper_id):
            assert paper_id == "arxiv:missing"
            return None

    client = TestClient(
        create_app(
            _settings(tmp_path),
            call_tool_fn=lambda *_args: {},
            read_store=FakeReadStore(),
        )
    )

    response = client.get("/api/papers/arxiv:missing")

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "NOT_FOUND"


def test_chunk_detail_endpoint_redacts_storage_paths(tmp_path):
    from paper_rag.workbench.api import create_app

    class FakeReadStore:
        def chunk_detail(self, chunk_id):
            assert chunk_id == "chunk-a"
            return {
                "chunk": {
                    "chunk_id": "chunk-a",
                    "paper_id": "arxiv:2310.11511",
                    "text": "Evidence text.",
                    "warnings": [],
                },
                "paper": {"paper_id": "arxiv:2310.11511", "title": "Self-RAG"},
                "neighbors": [],
            }

    client = TestClient(
        create_app(
            _settings(tmp_path),
            call_tool_fn=lambda *_args: {},
            read_store=FakeReadStore(),
        )
    )

    payload = client.get("/api/chunks/chunk-a").json()

    assert payload["chunk"]["chunk_id"] == "chunk-a"
    assert "source_path" not in str(payload)
    assert "asset_path" not in str(payload)


def test_dsh_handoff_builds_prompt_without_calling_tools(tmp_path):
    from paper_rag.workbench.api import create_app

    calls = []

    def fake_call_tool(name, args, ctx):
        calls.append((name, args, ctx))
        return {"structuredContent": {"ok": True, "tool": name, "data": {}}}

    client = TestClient(create_app(_settings(tmp_path), call_tool_fn=fake_call_tool))

    response = client.post(
        "/api/dsh/handoff",
        json={
            "question": "Self-RAG 的核心理念是什么？",
            "paper_ids": ["arxiv:2310.11511"],
            "chunk_ids": ["chunk-a"],
            "source": "ask",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dsh_url"] == "http://127.0.0.1:3080"
    assert "arxiv:2310.11511" in payload["prompt"]
    assert "chunk-a" in payload["prompt"]
    assert "证据引用" in payload["prompt"]
    assert calls == []
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_workbench_api.py
```

Expected: failures for unsupported `create_app` arguments and missing endpoints.

- [ ] **Step 3: Add `DshHandoffRequest` to schemas**

Modify `src/paper_rag/workbench/schemas.py`:

```python
class DshHandoffRequest(StrictRequest):
    question: str = Field(..., min_length=1, max_length=4000)
    paper_ids: list[str] = Field(default_factory=list, max_length=12)
    chunk_ids: list[str] = Field(default_factory=list, max_length=20)
    source: str = Field("workbench", max_length=80)
```

- [ ] **Step 4: Implement diagnostics**

Create `src/paper_rag/workbench/diagnostics.py`:

```python
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from paper_rag import config as cfg
from paper_rag.workbench.credentials import credential_status
from paper_rag.workbench.read_store import WorkbenchReadStore
from paper_rag.workbench.settings import WorkbenchSettings


def build_index_health(
    settings: WorkbenchSettings,
    *,
    read_store: WorkbenchReadStore | None = None,
) -> dict[str, Any]:
    store = read_store or WorkbenchReadStore()
    config = cfg.load()
    quality = store.corpus_quality()
    sqlite_summary = _sqlite_summary(store)
    qdrant = _qdrant_summary(config)
    credentials = credential_status(credentials_path=settings.credentials_path).as_dict()
    llm = {
        "configured": bool(settings.openai_base_url and settings.chat_model and credentials["configured"]),
        "chat_model": settings.chat_model,
        "base_url_host": urlparse(settings.openai_base_url).netloc or None,
        "credential_source": credentials["source"],
    }
    retrieval = {
        "dense_available": bool(qdrant["reachable"]),
        "sparse_available": bool(sqlite_summary["available"]),
        "hybrid_available": bool(sqlite_summary["available"]),
    }
    warnings = _warnings(sqlite_summary, qdrant, llm, quality)
    status = _overall_status(sqlite_summary, qdrant, llm)
    return {
        "status": status,
        "sqlite": sqlite_summary,
        "qdrant": qdrant,
        "retrieval": retrieval,
        "llm": llm,
        "corpus_quality": quality,
        "warnings": warnings,
    }


def _sqlite_summary(store: WorkbenchReadStore) -> dict[str, Any]:
    quality = store.corpus_quality(limit=1)
    return {
        "available": True,
        "paper_count": int(quality.get("paper_count", 0)),
        "chunk_count": int(quality.get("chunk_count", 0)),
        "fts_available": True,
    }


def _qdrant_summary(config) -> dict[str, Any]:
    qdrant = config.qdrant
    mode = "none"
    if getattr(qdrant, "local_path", None) or str(qdrant.url or "").startswith(("file://", "local://")):
        mode = "embedded"
    elif qdrant.url:
        mode = "server"
    reachable = False
    degraded_reason = None
    try:
        from paper_rag.store.qdrant_store import get_client

        client = get_client()
        client.get_collections()
        reachable = True
    except Exception as exc:  # noqa: BLE001
        degraded_reason = f"{type(exc).__name__}: {exc}"
    return {
        "configured": bool(qdrant.url or getattr(qdrant, "local_path", None)),
        "mode": mode,
        "reachable": reachable,
        "collection_chunks": qdrant.collection_chunks,
        "degraded_reason": degraded_reason,
    }


def _overall_status(sqlite_summary, qdrant, llm) -> str:
    if not sqlite_summary["available"] or not llm["configured"]:
        return "blocked"
    if not qdrant["reachable"]:
        return "degraded"
    return "healthy"


def _warnings(sqlite_summary, qdrant, llm, quality) -> list[str]:
    warnings: list[str] = []
    if not qdrant["reachable"]:
        warnings.append("Dense retrieval is unavailable; sparse fallback is active.")
    if quality["duplicate_chunk_count"]:
        warnings.append("Duplicate chunks detected in the corpus.")
    if quality["parser_artifact_count"]:
        warnings.append("Parser artifacts detected in indexed chunks.")
    if not llm["configured"]:
        warnings.append("LLM generation is not configured.")
    return warnings
```

- [ ] **Step 5: Add endpoints and dependency injection to `api.py`**

Modify imports:

```python
from .diagnostics import build_index_health
from .read_store import WorkbenchReadStore
from .schemas import DshHandoffRequest
```

Extend `create_app`:

```python
def create_app(
    settings: WorkbenchSettings | None = None,
    *,
    call_tool_fn: CallTool = call_tool,
    index_health_fn: Callable[[WorkbenchSettings], dict[str, Any]] = build_index_health,
    read_store: WorkbenchReadStore | None = None,
) -> FastAPI:
```

Inside `create_app`, after `app_settings`:

```python
    store = read_store or WorkbenchReadStore()
```

Add endpoint handlers:

```python
    @app.get("/api/health/index")
    def index_health() -> dict[str, Any]:
        return index_health_fn(app_settings)

    @app.get("/api/papers/{paper_id:path}")
    def paper_detail(paper_id: str) -> dict[str, Any]:
        try:
            detail = store.paper_detail(paper_id)
        except ValueError as exc:
            raise _http_error(400, "BAD_REQUEST", str(exc)) from exc
        if detail is None:
            raise _http_error(404, "NOT_FOUND", f"Paper not found: {paper_id}")
        return detail

    @app.get("/api/chunks/{chunk_id}")
    def chunk_detail(chunk_id: str) -> dict[str, Any]:
        try:
            detail = store.chunk_detail(chunk_id)
        except ValueError as exc:
            raise _http_error(400, "BAD_REQUEST", str(exc)) from exc
        if detail is None:
            raise _http_error(404, "NOT_FOUND", f"Chunk not found: {chunk_id}")
        return detail

    @app.post("/api/dsh/handoff")
    def dsh_handoff(payload: DshHandoffRequest) -> dict[str, Any]:
        prompt = _build_dsh_prompt(payload)
        return {"dsh_url": app_settings.dsh_url, "prompt": prompt}
```

Add helper functions below `mcp_envelope`:

```python
def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "ok": False,
            "error": {
                "code": code,
                "message": message,
                "retryable": False,
            },
        },
    )


def _build_dsh_prompt(payload: DshHandoffRequest) -> str:
    papers = ", ".join(payload.paper_ids) if payload.paper_ids else "未指定"
    chunks = ", ".join(payload.chunk_ids) if payload.chunk_ids else "未指定"
    return (
        "基于 Paper RAG Workbench 中选定的论文/证据继续研究：\n"
        f"- Source: {payload.source}\n"
        f"- Papers: {papers}\n"
        f"- Chunks: {chunks}\n"
        f"- Question: {payload.question.strip()}\n"
        "请使用 Paper RAG 工具回答，并保留证据引用。"
    )
```

If mypy or ruff flags the `Callable[[WorkbenchSettings], dict[str, Any]]` type, introduce `IndexHealthBuilder = Callable[[WorkbenchSettings], dict[str, Any]]` beside `CallTool`.

- [ ] **Step 6: Run backend tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_workbench_read_store.py tests/test_workbench_api.py
```

Expected: all selected backend tests pass.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add src/paper_rag/workbench/diagnostics.py src/paper_rag/workbench/api.py src/paper_rag/workbench/schemas.py tests/test_workbench_api.py tests/test_workbench_read_store.py
git commit -m "feat: add workbench v2 api endpoints"
```

---

### Task 3: Frontend Contracts, Client, And Fixtures

**Files:**
- Modify: `integrations/paper-rag-workbench/src/types.ts`
- Modify: `integrations/paper-rag-workbench/src/api/client.ts`
- Modify: `integrations/paper-rag-workbench/src/api/fixtures.ts`
- Modify: `integrations/paper-rag-workbench/src/__tests__/client.test.ts`

**Interfaces:**
- Consumes: Backend endpoints from Task 2.
- Produces: `WorkbenchClient.indexHealth()`
- Produces: `WorkbenchClient.paperDetail(paperId: string)`
- Produces: `WorkbenchClient.chunkDetail(chunkId: string)`
- Produces: `WorkbenchClient.dshHandoff(input: DshHandoffInput)`
- Produces: fixture exports `indexHealthFixture`, `paperDetailFixture`, `chunkDetailFixture`, `dshHandoffFixture`

- [ ] **Step 1: Write failing client tests**

Extend `integrations/paper-rag-workbench/src/__tests__/client.test.ts` with:

```ts
test("client reads v2 endpoints", async () => {
  const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/api/health/index")) {
      return new Response(JSON.stringify({ status: "healthy", warnings: [] }), { status: 200 });
    }
    if (url.endsWith("/api/papers/arxiv%3A2310.11511")) {
      return new Response(JSON.stringify({ paper: { paper_id: "arxiv:2310.11511" }, sections: [], chunks: [] }), { status: 200 });
    }
    if (url.endsWith("/api/chunks/chunk-a")) {
      return new Response(JSON.stringify({ chunk: { chunk_id: "chunk-a" }, paper: {}, neighbors: [] }), { status: 200 });
    }
    if (url.endsWith("/api/dsh/handoff") && init?.method === "POST") {
      return new Response(JSON.stringify({ dsh_url: "http://127.0.0.1:3080", prompt: "prompt" }), { status: 200 });
    }
    return new Response("not found", { status: 404 });
  });

  const client = createWorkbenchClient({ fetchImpl, baseUrl: "" });

  await expect(client.indexHealth()).resolves.toMatchObject({ status: "healthy" });
  await expect(client.paperDetail("arxiv:2310.11511")).resolves.toMatchObject({
    paper: { paper_id: "arxiv:2310.11511" },
  });
  await expect(client.chunkDetail("chunk-a")).resolves.toMatchObject({
    chunk: { chunk_id: "chunk-a" },
  });
  await expect(
    client.dshHandoff({
      question: "Question?",
      paper_ids: ["arxiv:2310.11511"],
      chunk_ids: ["chunk-a"],
      source: "ask",
    }),
  ).resolves.toMatchObject({ prompt: "prompt" });
});
```

- [ ] **Step 2: Run frontend client tests to verify they fail**

Run:

```bash
pnpm --dir integrations/paper-rag-workbench test src/__tests__/client.test.ts
```

Expected: failure because the new client methods do not exist.

- [ ] **Step 3: Add frontend types**

Extend `integrations/paper-rag-workbench/src/types.ts`:

```ts
export type HealthStatus = "healthy" | "degraded" | "blocked";

export type HealthSample = {
  kind: "duplicate_chunk" | "parser_artifact" | "missing_section" | string;
  paper_id?: string;
  chunk_id?: string;
  chunk_ids?: string[];
  warnings?: string[];
  preview?: string;
};

export type IndexHealthData = {
  status: HealthStatus;
  sqlite: {
    available: boolean;
    paper_count: number;
    chunk_count: number;
    fts_available: boolean;
  };
  qdrant: {
    configured: boolean;
    mode: "server" | "embedded" | "none";
    reachable: boolean;
    collection_chunks?: string;
    degraded_reason?: string | null;
  };
  retrieval: {
    dense_available: boolean;
    sparse_available: boolean;
    hybrid_available: boolean;
  };
  llm: {
    configured: boolean;
    chat_model: string;
    base_url_host?: string | null;
    credential_source?: "env" | "file" | null;
  };
  corpus_quality: {
    duplicate_chunk_count: number;
    parser_artifact_count: number;
    missing_section_count: number;
    samples: HealthSample[];
  };
  warnings: string[];
};

export type PaperSectionSummary = {
  section_id: string;
  name: string;
  idx: number;
  page_start?: number | null;
  page_end?: number | null;
  chunk_count: number;
};

export type PaperDetailData = {
  paper: PaperSummary & {
    abstract?: string | null;
    year?: number | null;
    venue?: string | null;
    doi?: string | null;
    status?: string;
    parsed_with?: string | null;
    updated_at?: string;
  };
  sections: PaperSectionSummary[];
  chunks: EvidenceChunk[];
  warnings: string[];
};

export type ChunkDetailData = {
  chunk: EvidenceChunk & { warnings?: string[]; char_start?: number | null; char_end?: number | null };
  paper: PaperSummary;
  neighbors: EvidenceChunk[];
};

export type DshHandoffInput = {
  question: string;
  paper_ids: string[];
  chunk_ids: string[];
  source: "ask" | "search" | "library" | "health" | "workbench";
};

export type DshHandoffData = {
  dsh_url: string;
  prompt: string;
};
```

Extend `WorkbenchClient`:

```ts
  indexHealth(): Promise<IndexHealthData>;
  paperDetail(paperId: string): Promise<PaperDetailData>;
  chunkDetail(chunkId: string): Promise<ChunkDetailData>;
  dshHandoff(input: DshHandoffInput): Promise<DshHandoffData>;
```

- [ ] **Step 4: Add client methods**

Modify `integrations/paper-rag-workbench/src/api/client.ts`:

```ts
import {
  chunkDetailFixture,
  dshHandoffFixture,
  indexHealthFixture,
  paperDetailFixture,
} from "./fixtures";
```

Add returned methods:

```ts
    indexHealth: (): Promise<IndexHealthData> =>
      fixtureMode ? Promise.resolve(indexHealthFixture) : get("/api/health/index"),
    paperDetail: (paperId: string): Promise<PaperDetailData> =>
      fixtureMode
        ? Promise.resolve(paperDetailFixture)
        : get(`/api/papers/${encodeURIComponent(paperId)}`),
    chunkDetail: (chunkId: string): Promise<ChunkDetailData> =>
      fixtureMode ? Promise.resolve(chunkDetailFixture) : get(`/api/chunks/${encodeURIComponent(chunkId)}`),
    dshHandoff: (input: DshHandoffInput): Promise<DshHandoffData> =>
      fixtureMode ? Promise.resolve(dshHandoffFixture) : post("/api/dsh/handoff", input),
```

Ensure the type imports include `IndexHealthData`, `PaperDetailData`, `ChunkDetailData`, `DshHandoffInput`, and `DshHandoffData`.

- [ ] **Step 5: Add fixture data**

Extend `integrations/paper-rag-workbench/src/api/fixtures.ts`:

```ts
export const indexHealthFixture: IndexHealthData = {
  status: "degraded",
  sqlite: { available: true, paper_count: 8, chunk_count: 345, fts_available: true },
  qdrant: {
    configured: true,
    mode: "server",
    reachable: false,
    collection_chunks: "paper_chunks",
    degraded_reason: "connection refused",
  },
  retrieval: { dense_available: false, sparse_available: true, hybrid_available: true },
  llm: {
    configured: true,
    chat_model: "deepseek-v4-flash",
    base_url_host: "api.deepseek.com",
    credential_source: "file",
  },
  corpus_quality: {
    duplicate_chunk_count: 1,
    parser_artifact_count: 1,
    missing_section_count: 0,
    samples: [
      {
        kind: "duplicate_chunk",
        paper_id: "arxiv:2310.11511",
        chunk_ids: ["05e56a78", "f2d5041b"],
        preview: "SELF-RAG retrieves passages on demand.",
      },
      {
        kind: "parser_artifact",
        paper_id: "arxiv:2310.11511",
        chunk_id: "chunk-self-rag-1",
        warnings: ["html_comment"],
        preview: "<!-- page 2 --> Introduction text.",
      },
    ],
  },
  warnings: ["Dense retrieval is unavailable; sparse fallback is active."],
};

export const paperDetailFixture: PaperDetailData = {
  paper: {
    paper_id: "arxiv:2310.11511",
    title: "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection",
    arxiv_id: "2310.11511",
    year: 2023,
    abstract: "SELF-RAG trains a model to retrieve and critique evidence.",
    chunk_count: 58,
    status: "done",
    parsed_with: "pymupdf",
  },
  sections: [
    { section_id: "sec-abstract", name: "Abstract", idx: 0, page_start: 1, page_end: 1, chunk_count: 1 },
    { section_id: "sec-intro", name: "Introduction", idx: 1, page_start: 1, page_end: 2, chunk_count: 3 },
  ],
  chunks: searchFixture.data!.results,
  warnings: ["parser_artifacts_detected"],
};

export const chunkDetailFixture: ChunkDetailData = {
  chunk: {
    ...searchFixture.data!.results[0],
    text: "SELF-RAG retrieves passages on demand and critiques its own generations.",
    warnings: ["html_comment"],
  },
  paper: paperDetailFixture.paper,
  neighbors: [searchFixture.data!.results[1]],
};

export const dshHandoffFixture: DshHandoffData = {
  dsh_url: "http://127.0.0.1:3080",
  prompt:
    "基于 Paper RAG Workbench 中选定的论文/证据继续研究：\n- Papers: arxiv:2310.11511\n- Chunks: chunk-self-rag-1\n- Question: What is Self-RAG?\n请使用 Paper RAG 工具回答，并保留证据引用。",
};
```

Add the needed type imports at the top of the fixture file.

- [ ] **Step 6: Run frontend client tests**

Run:

```bash
pnpm --dir integrations/paper-rag-workbench test src/__tests__/client.test.ts
```

Expected: client tests pass.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add integrations/paper-rag-workbench/src/types.ts integrations/paper-rag-workbench/src/api/client.ts integrations/paper-rag-workbench/src/api/fixtures.ts integrations/paper-rag-workbench/src/__tests__/client.test.ts
git commit -m "feat: add workbench v2 frontend contracts"
```

---

### Task 4: Health Page

**Files:**
- Create: `integrations/paper-rag-workbench/src/components/WarningBanner.tsx`
- Create: `integrations/paper-rag-workbench/src/components/DiagnosticCard.tsx`
- Create: `integrations/paper-rag-workbench/src/components/HealthSummary.tsx`
- Create: `integrations/paper-rag-workbench/src/components/QualityIssueTable.tsx`
- Create: `integrations/paper-rag-workbench/src/pages/HealthPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/App.tsx`
- Modify: `integrations/paper-rag-workbench/src/components/Shell.tsx`
- Modify: `integrations/paper-rag-workbench/src/pages/OverviewPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/styles.css`
- Modify: `integrations/paper-rag-workbench/src/__tests__/components.test.tsx`
- Modify: `integrations/paper-rag-workbench/src/__tests__/pages.test.tsx`

**Interfaces:**
- Consumes: `WorkbenchClient.indexHealth()` from Task 3.
- Produces: `HealthPage({ client }: { client: WorkbenchClient })`.
- Produces: reusable diagnostic components for later pages.

- [ ] **Step 1: Write failing component tests**

Add to `components.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";

import { HealthSummary } from "../components/HealthSummary";
import { QualityIssueTable } from "../components/QualityIssueTable";
import { indexHealthFixture } from "../api/fixtures";

test("health summary distinguishes degraded services", () => {
  render(<HealthSummary data={indexHealthFixture} />);

  expect(screen.getByRole("heading", { name: /index health/i })).toBeInTheDocument();
  expect(screen.getByText(/degraded/i)).toBeInTheDocument();
  expect(screen.getByText(/sparse fallback/i)).toBeInTheDocument();
  expect(screen.getByText("deepseek-v4-flash")).toBeInTheDocument();
});

test("quality issue table shows duplicate and parser samples", () => {
  render(<QualityIssueTable samples={indexHealthFixture.corpus_quality.samples} />);

  expect(screen.getByText(/duplicate_chunk/i)).toBeInTheDocument();
  expect(screen.getByText(/parser_artifact/i)).toBeInTheDocument();
  expect(screen.getByText(/05e56a78/)).toBeInTheDocument();
});
```

Add to `pages.test.tsx`:

```tsx
import { HealthPage } from "../pages/HealthPage";

test("health page loads index diagnostics", async () => {
  render(<HealthPage client={createWorkbenchClient({ fixtureMode: true })} />);

  await waitForElementToBeRemoved(() => screen.queryByText(/loading health/i));

  expect(screen.getByRole("heading", { name: "Health" })).toBeInTheDocument();
  expect(screen.getByText(/Dense retrieval is unavailable/i)).toBeInTheDocument();
  expect(screen.getByText(/345/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run frontend tests to verify they fail**

Run:

```bash
pnpm --dir integrations/paper-rag-workbench test src/__tests__/components.test.tsx src/__tests__/pages.test.tsx
```

Expected: failures because the Health components and page do not exist.

- [ ] **Step 3: Implement warning and diagnostic components**

Create `WarningBanner.tsx`:

```tsx
export function WarningBanner({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <div className="warning-banner" role="status">
      {warnings.map((warning) => (
        <p key={warning}>{warning}</p>
      ))}
    </div>
  );
}
```

Create `DiagnosticCard.tsx`:

```tsx
import type { ReactNode } from "react";

export function DiagnosticCard({
  title,
  status,
  children,
}: {
  title: string;
  status: string;
  children: ReactNode;
}) {
  return (
    <section className="diagnostic-card" aria-label={title}>
      <header>
        <h3>{title}</h3>
        <span className={`status-pill ${status.toLowerCase()}`}>{status}</span>
      </header>
      <div>{children}</div>
    </section>
  );
}
```

Create `HealthSummary.tsx`:

```tsx
import type { IndexHealthData } from "../types";
import { DiagnosticCard } from "./DiagnosticCard";
import { WarningBanner } from "./WarningBanner";

export function HealthSummary({ data }: { data: IndexHealthData }) {
  return (
    <section className="health-summary">
      <header>
        <h3>Index Health</h3>
        <span className={`status-pill ${data.status}`}>{data.status}</span>
      </header>
      <WarningBanner warnings={data.warnings} />
      <div className="diagnostic-grid">
        <DiagnosticCard title="SQLite" status={data.sqlite.available ? "healthy" : "blocked"}>
          <dl>
            <dt>Papers</dt>
            <dd>{data.sqlite.paper_count}</dd>
            <dt>Chunks</dt>
            <dd>{data.sqlite.chunk_count}</dd>
            <dt>FTS</dt>
            <dd>{data.sqlite.fts_available ? "available" : "unavailable"}</dd>
          </dl>
        </DiagnosticCard>
        <DiagnosticCard title="Qdrant" status={data.qdrant.reachable ? "healthy" : "degraded"}>
          <dl>
            <dt>Mode</dt>
            <dd>{data.qdrant.mode}</dd>
            <dt>Dense</dt>
            <dd>{data.retrieval.dense_available ? "available" : "unavailable"}</dd>
            <dt>Fallback</dt>
            <dd>{data.retrieval.sparse_available ? "sparse fallback active" : "unavailable"}</dd>
          </dl>
        </DiagnosticCard>
        <DiagnosticCard title="LLM" status={data.llm.configured ? "healthy" : "blocked"}>
          <dl>
            <dt>Model</dt>
            <dd>{data.llm.chat_model}</dd>
            <dt>Host</dt>
            <dd>{data.llm.base_url_host || "not configured"}</dd>
            <dt>Credentials</dt>
            <dd>{data.llm.credential_source || "not configured"}</dd>
          </dl>
        </DiagnosticCard>
      </div>
    </section>
  );
}
```

Create `QualityIssueTable.tsx`:

```tsx
import type { HealthSample } from "../types";

export function QualityIssueTable({ samples }: { samples: HealthSample[] }) {
  if (samples.length === 0) {
    return <p className="muted">No quality samples detected.</p>;
  }
  return (
    <table className="quality-table">
      <thead>
        <tr>
          <th>Kind</th>
          <th>Paper</th>
          <th>Chunks</th>
          <th>Preview</th>
        </tr>
      </thead>
      <tbody>
        {samples.map((sample, index) => (
          <tr key={`${sample.kind}-${sample.chunk_id || sample.chunk_ids?.join("-") || index}`}>
            <td>{sample.kind}</td>
            <td>{sample.paper_id || "unknown"}</td>
            <td>{sample.chunk_id || sample.chunk_ids?.join(", ") || "unknown"}</td>
            <td>{sample.preview || sample.warnings?.join(", ") || ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Implement `HealthPage` and navigation**

Create `HealthPage.tsx`:

```tsx
import { useEffect, useState } from "react";

import { EmptyState } from "../components/EmptyState";
import { HealthSummary } from "../components/HealthSummary";
import { QualityIssueTable } from "../components/QualityIssueTable";
import type { IndexHealthData, WorkbenchClient } from "../types";

export function HealthPage({ client }: { client: WorkbenchClient }) {
  const [data, setData] = useState<IndexHealthData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    client
      .indexHealth()
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Health unavailable.");
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  return (
    <>
      <header className="page-header">
        <div>
          <h2>Health</h2>
          <p>Inspect corpus readiness, retrieval fallback, model configuration, and data quality.</p>
        </div>
      </header>
      {!data && !error ? <EmptyState title="Loading health" detail="Checking local indexes." /> : null}
      {error ? <EmptyState title="Health unavailable" detail={error} /> : null}
      {data ? (
        <>
          <HealthSummary data={data} />
          <section className="panel">
            <h3>Quality Issues</h3>
            <QualityIssueTable samples={data.corpus_quality.samples} />
          </section>
        </>
      ) : null}
    </>
  );
}
```

Modify `Shell.tsx`:

```tsx
import { Activity, BookOpen, Compass, Database, MessageSquare, Search, Sparkles } from "lucide-react";

const nav = [
  { id: "overview", label: "Overview", icon: Database },
  { id: "health", label: "Health", icon: Activity },
  { id: "library", label: "Library", icon: BookOpen },
  { id: "search", label: "Search", icon: Search },
  { id: "ask", label: "Ask", icon: MessageSquare },
  { id: "discover", label: "Discover", icon: Compass },
  { id: "dsh", label: "DSH Chat", icon: Sparkles },
] as const;
```

Modify `App.tsx`:

```tsx
import { HealthPage } from "./pages/HealthPage";

{route === "health" ? <HealthPage client={client} /> : null}
```

Update `OverviewPage.tsx` so degraded health is visible from the first screen:

```tsx
import { HealthSummary } from "../components/HealthSummary";
import type { IndexHealthData, StatusData, WorkbenchClient } from "../types";

const [health, setHealth] = useState<IndexHealthData | null>(null);

useEffect(() => {
  let active = true;
  client.indexHealth().then((next) => {
    if (active) setHealth(next);
  });
  return () => {
    active = false;
  };
}, [client]);

{health ? <HealthSummary data={health} /> : null}
```

- [ ] **Step 5: Add styles**

Add classes to `styles.css`:

```css
.warning-banner {
  border: 1px solid #8a6d1f;
  background: #fff4d6;
  color: #7a5200;
  border-radius: 8px;
  padding: 12px 14px;
  margin: 12px 0;
}

.warning-banner p {
  margin: 0;
}

.diagnostic-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.diagnostic-card {
  border: 1px solid #dde4eb;
  border-radius: 8px;
  padding: 14px;
  background: #ffffff;
}

.diagnostic-card header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.status-pill.healthy {
  color: #17663a;
}

.status-pill.degraded {
  color: #7a5200;
}

.status-pill.blocked {
  color: #9b1c1c;
}

.quality-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.quality-table th,
.quality-table td {
  border-bottom: 1px solid #dde4eb;
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}
```

- [ ] **Step 6: Run frontend tests**

Run:

```bash
pnpm --dir integrations/paper-rag-workbench test src/__tests__/components.test.tsx src/__tests__/pages.test.tsx
```

Expected: selected frontend tests pass.

- [ ] **Step 7: Commit Task 4**

Run:

```bash
git add integrations/paper-rag-workbench/src/App.tsx integrations/paper-rag-workbench/src/components/Shell.tsx integrations/paper-rag-workbench/src/components/WarningBanner.tsx integrations/paper-rag-workbench/src/components/DiagnosticCard.tsx integrations/paper-rag-workbench/src/components/HealthSummary.tsx integrations/paper-rag-workbench/src/components/QualityIssueTable.tsx integrations/paper-rag-workbench/src/pages/HealthPage.tsx integrations/paper-rag-workbench/src/pages/OverviewPage.tsx integrations/paper-rag-workbench/src/styles.css integrations/paper-rag-workbench/src/__tests__/components.test.tsx integrations/paper-rag-workbench/src/__tests__/pages.test.tsx
git commit -m "feat: add workbench health page"
```

---

### Task 5: Paper Detail And Citation Drilldown

**Files:**
- Create: `integrations/paper-rag-workbench/src/components/PaperDetailPanel.tsx`
- Create: `integrations/paper-rag-workbench/src/components/ChunkDetailPanel.tsx`
- Create: `integrations/paper-rag-workbench/src/components/ScoreBreakdown.tsx`
- Modify: `integrations/paper-rag-workbench/src/components/EvidenceChunkCard.tsx`
- Modify: `integrations/paper-rag-workbench/src/components/CitationChips.tsx`
- Modify: `integrations/paper-rag-workbench/src/components/AnswerPanel.tsx`
- Modify: `integrations/paper-rag-workbench/src/pages/AskPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/pages/SearchPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/pages/LibraryPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/styles.css`
- Modify: `integrations/paper-rag-workbench/src/__tests__/components.test.tsx`
- Modify: `integrations/paper-rag-workbench/src/__tests__/pages.test.tsx`

**Interfaces:**
- Consumes: `client.paperDetail(paperId)` and `client.chunkDetail(chunkId)`.
- Produces: inspectable paper panel reachable from Library/Search/Ask.
- Produces: inspectable chunk drilldown reachable from citations and evidence cards.

- [ ] **Step 1: Write failing component tests**

Add to `components.test.tsx`:

```tsx
import { ChunkDetailPanel } from "../components/ChunkDetailPanel";
import { PaperDetailPanel } from "../components/PaperDetailPanel";
import { ScoreBreakdown } from "../components/ScoreBreakdown";
import { chunkDetailFixture, paperDetailFixture } from "../api/fixtures";

test("paper detail panel lists sections and chunks", () => {
  render(<PaperDetailPanel detail={paperDetailFixture} onInspectChunk={() => {}} />);

  expect(screen.getByRole("heading", { name: /Self-RAG/i })).toBeInTheDocument();
  expect(screen.getByText("Abstract")).toBeInTheDocument();
  expect(screen.getByText("Introduction")).toBeInTheDocument();
  expect(screen.getByText(/parser_artifacts_detected/i)).toBeInTheDocument();
});

test("chunk detail panel shows full text and neighbors", () => {
  render(<ChunkDetailPanel detail={chunkDetailFixture} onOpenPaper={() => {}} />);

  expect(screen.getByText(/critiques its own generations/i)).toBeInTheDocument();
  expect(screen.getByText(/html_comment/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /open paper detail/i })).toBeInTheDocument();
});

test("score breakdown renders known score fields", () => {
  render(<ScoreBreakdown chunk={{ ...chunkDetailFixture.chunk, score: 0.92, dense_score: 0.81, sparse_score: 0.74 }} />);

  expect(screen.getByText(/score 0.92/i)).toBeInTheDocument();
  expect(screen.getByText(/dense 0.81/i)).toBeInTheDocument();
  expect(screen.getByText(/sparse 0.74/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Write failing page tests**

Add to `pages.test.tsx`:

```tsx
test("library opens paper detail", async () => {
  const user = userEvent.setup();
  render(<LibraryPage client={createWorkbenchClient({ fixtureMode: true })} />);

  await waitForElementToBeRemoved(() => screen.queryByText(/loading library/i));
  await user.click(screen.getByRole("button", { name: /inspect paper self-rag/i }));

  expect(await screen.findByRole("heading", { name: /Self-RAG/i })).toBeInTheDocument();
  expect(screen.getByText(/Abstract/)).toBeInTheDocument();
});

test("ask citation opens chunk drilldown", async () => {
  const user = userEvent.setup();
  render(<AskPage client={createWorkbenchClient({ fixtureMode: true })} />);

  await user.type(screen.getByLabelText(/question/i), "What is Self-RAG?");
  await user.click(screen.getByRole("button", { name: /^ask$/i }));
  await user.click(await screen.findByRole("button", { name: /chunk-self-rag-1/i }));

  expect(await screen.findByText(/critiques its own generations/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /open paper detail/i })).toBeInTheDocument();
});

test("search evidence card opens chunk drilldown", async () => {
  const user = userEvent.setup();
  render(<SearchPage client={createWorkbenchClient({ fixtureMode: true })} />);

  await user.type(screen.getByLabelText(/search evidence/i), "reflection tokens");
  await user.click(screen.getByRole("button", { name: /^search$/i }));
  await user.click(await screen.findByRole("button", { name: /inspect chunk chunk-self-rag-1/i }));

  expect(await screen.findByText(/critiques its own generations/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Run frontend tests to verify they fail**

Run:

```bash
pnpm --dir integrations/paper-rag-workbench test src/__tests__/components.test.tsx src/__tests__/pages.test.tsx
```

Expected: failures because panel components and actions do not exist.

- [ ] **Step 4: Implement detail components**

Create `ScoreBreakdown.tsx`:

```tsx
import type { EvidenceChunk } from "../types";

export function ScoreBreakdown({ chunk }: { chunk: EvidenceChunk & Record<string, unknown> }) {
  const pairs = [
    ["score", chunk.score],
    ["dense", chunk.dense_score],
    ["sparse", chunk.sparse_score],
    ["rrf", chunk.rrf_score],
    ["rerank", chunk.rerank_score],
  ].filter((item): item is [string, number] => typeof item[1] === "number");

  if (pairs.length === 0) return null;
  return (
    <dl className="score-breakdown">
      {pairs.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{label} {value.toFixed(2)}</dd>
        </div>
      ))}
    </dl>
  );
}
```

Create `PaperDetailPanel.tsx`:

```tsx
import type { PaperDetailData } from "../types";

export function PaperDetailPanel({
  detail,
  onInspectChunk,
}: {
  detail: PaperDetailData;
  onInspectChunk: (chunkId: string) => void;
}) {
  return (
    <section className="paper-detail panel">
      <header>
        <h3>{detail.paper.title}</h3>
        <code>{detail.paper.paper_id}</code>
      </header>
      {detail.warnings.length ? (
        <div className="inline-warnings">
          {detail.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
      {detail.paper.abstract ? <p>{detail.paper.abstract}</p> : null}
      <section>
        <h4>Sections</h4>
        <ul className="section-list">
          {detail.sections.map((section) => (
            <li key={section.section_id}>
              <strong>{section.name}</strong>
              <span>{section.chunk_count} chunks</span>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h4>Chunks</h4>
        <div className="chunk-list">
          {detail.chunks.map((chunk) => (
            <button key={chunk.chunk_id} type="button" onClick={() => onInspectChunk(chunk.chunk_id)}>
              <span>{chunk.section || "Unknown section"}</span>
              <code>chunk:{chunk.chunk_id}</code>
              <span>{chunk.snippet || chunk.text}</span>
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}
```

Create `ChunkDetailPanel.tsx`:

```tsx
import type { ChunkDetailData } from "../types";
import { ScoreBreakdown } from "./ScoreBreakdown";

export function ChunkDetailPanel({
  detail,
  onOpenPaper,
}: {
  detail: ChunkDetailData;
  onOpenPaper: (paperId: string) => void;
}) {
  const warnings = detail.chunk.warnings || [];
  return (
    <aside className="chunk-detail panel" aria-label="Chunk detail">
      <header>
        <div>
          <h3>{detail.paper.title || detail.chunk.paper_id}</h3>
          <code>chunk:{detail.chunk.chunk_id}</code>
        </div>
        <button type="button" onClick={() => onOpenPaper(detail.chunk.paper_id)}>
          Open paper detail
        </button>
      </header>
      <dl className="metadata-grid">
        <dt>Paper</dt>
        <dd>{detail.chunk.paper_id}</dd>
        <dt>Section</dt>
        <dd>{detail.chunk.section || "unknown"}</dd>
        <dt>Page</dt>
        <dd>{detail.chunk.page || "unknown"}</dd>
      </dl>
      <ScoreBreakdown chunk={detail.chunk} />
      {warnings.length ? (
        <div className="inline-warnings">
          {warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
      <p className="chunk-full-text">{detail.chunk.text || detail.chunk.snippet}</p>
      {detail.neighbors.length ? (
        <section>
          <h4>Nearby chunks</h4>
          {detail.neighbors.map((neighbor) => (
            <article key={neighbor.chunk_id}>
              <code>chunk:{neighbor.chunk_id}</code>
              <p>{neighbor.text || neighbor.snippet}</p>
            </article>
          ))}
        </section>
      ) : null}
    </aside>
  );
}
```

- [ ] **Step 5: Wire inspect actions into pages**

Modify `EvidenceChunkCard.tsx`:

```tsx
export function EvidenceChunkCard({
  chunk,
  onInspect,
}: {
  chunk: EvidenceChunk;
  onInspect?: (chunkId: string) => void;
}) {
```

Add a button in the footer:

```tsx
{onInspect ? (
  <button type="button" onClick={() => onInspect(chunk.chunk_id)}>
    Inspect chunk {chunk.chunk_id}
  </button>
) : null}
```

Modify `AnswerPanel.tsx` so it accepts `onCitationSelect?: (chunkId: string) => void` and passes it to `CitationChips`.

Modify `AskPage.tsx`:

```tsx
const [chunkDetail, setChunkDetail] = useState<ChunkDetailData | null>(null);
const [paperDetail, setPaperDetail] = useState<PaperDetailData | null>(null);

const inspectChunk = async (chunkId: string) => {
  setChunkDetail(await client.chunkDetail(chunkId));
};

const openPaper = async (paperId: string) => {
  setPaperDetail(await client.paperDetail(paperId));
};
```

Render:

```tsx
<AnswerPanel
  answer={data.answer}
  citations={data.citations}
  chunks={data.chunks}
  abstain={data.abstain}
  onCitationSelect={inspectChunk}
/>
{chunkDetail ? <ChunkDetailPanel detail={chunkDetail} onOpenPaper={openPaper} /> : null}
{paperDetail ? <PaperDetailPanel detail={paperDetail} onInspectChunk={inspectChunk} /> : null}
```

Modify `SearchPage.tsx` similarly, passing `onInspect={inspectChunk}` to each `EvidenceChunkCard`.

Modify `LibraryPage.tsx` to add an `Inspect paper ${paper.title}` button for each row and render `PaperDetailPanel` after `client.paperDetail(paper.paper_id)`.

- [ ] **Step 6: Add drilldown styles**

Add to `styles.css`:

```css
.paper-detail,
.chunk-detail {
  margin-top: 16px;
}

.section-list,
.chunk-list {
  display: grid;
  gap: 8px;
  padding: 0;
  list-style: none;
}

.chunk-list button {
  display: grid;
  gap: 6px;
  text-align: left;
  width: 100%;
}

.chunk-full-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.inline-warnings {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0;
}

.inline-warnings span {
  border: 1px solid #8a6d1f;
  border-radius: 999px;
  padding: 4px 8px;
  color: #f2d891;
}

.metadata-grid,
.score-breakdown {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 6px 12px;
}

.metadata-grid dd,
.score-breakdown dd {
  margin: 0;
  overflow-wrap: anywhere;
}
```

- [ ] **Step 7: Run frontend tests**

Run:

```bash
pnpm --dir integrations/paper-rag-workbench test src/__tests__/components.test.tsx src/__tests__/pages.test.tsx
```

Expected: selected frontend tests pass.

- [ ] **Step 8: Commit Task 5**

Run:

```bash
git add integrations/paper-rag-workbench/src/components/PaperDetailPanel.tsx integrations/paper-rag-workbench/src/components/ChunkDetailPanel.tsx integrations/paper-rag-workbench/src/components/ScoreBreakdown.tsx integrations/paper-rag-workbench/src/components/EvidenceChunkCard.tsx integrations/paper-rag-workbench/src/components/CitationChips.tsx integrations/paper-rag-workbench/src/components/AnswerPanel.tsx integrations/paper-rag-workbench/src/pages/AskPage.tsx integrations/paper-rag-workbench/src/pages/SearchPage.tsx integrations/paper-rag-workbench/src/pages/LibraryPage.tsx integrations/paper-rag-workbench/src/styles.css integrations/paper-rag-workbench/src/__tests__/components.test.tsx integrations/paper-rag-workbench/src/__tests__/pages.test.tsx
git commit -m "feat: add paper detail and citation drilldown"
```

---

### Task 6: DSH Handoff UX

**Files:**
- Create: `integrations/paper-rag-workbench/src/components/DshHandoffDialog.tsx`
- Modify: `integrations/paper-rag-workbench/src/pages/AskPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/pages/SearchPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/pages/LibraryPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/pages/HealthPage.tsx`
- Modify: `integrations/paper-rag-workbench/src/styles.css`
- Modify: `integrations/paper-rag-workbench/src/__tests__/components.test.tsx`
- Modify: `integrations/paper-rag-workbench/src/__tests__/pages.test.tsx`

**Interfaces:**
- Consumes: `client.dshHandoff(input)` from Task 3 and `/api/dsh/handoff` from Task 2.
- Produces: `DshHandoffDialog({ data, onClose }: { data: DshHandoffData; onClose: () => void })`.
- Produces: `Send to DSH` actions that copy a prompt and open `dsh_url`.

- [ ] **Step 1: Write failing DSH handoff tests**

Add to `components.test.tsx`:

```tsx
import { DshHandoffDialog } from "../components/DshHandoffDialog";
import { dshHandoffFixture } from "../api/fixtures";

test("dsh handoff dialog shows prompt and open link", () => {
  render(<DshHandoffDialog data={dshHandoffFixture} onClose={() => {}} />);

  expect(screen.getByRole("dialog", { name: /send to dsh/i })).toBeInTheDocument();
  expect(screen.getByText(/基于 Paper RAG Workbench/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /open dsh/i })).toHaveAttribute(
    "href",
    "http://127.0.0.1:3080",
  );
});
```

Add to `pages.test.tsx`:

```tsx
test("ask page creates a structured dsh handoff", async () => {
  const user = userEvent.setup();
  const baseClient = createWorkbenchClient({ fixtureMode: true });
  const dshHandoff = vi.fn(baseClient.dshHandoff);
  const client = { ...baseClient, dshHandoff };

  render(<AskPage client={client} />);

  await user.type(screen.getByLabelText(/question/i), "What is Self-RAG?");
  await user.click(screen.getByRole("button", { name: /^ask$/i }));
  await user.click(await screen.findByRole("button", { name: /send to dsh/i }));

  expect(dshHandoff).toHaveBeenCalledWith(
    expect.objectContaining({
      question: "What is Self-RAG?",
      paper_ids: expect.arrayContaining(["arxiv:2310.11511"]),
      chunk_ids: expect.arrayContaining(["chunk-self-rag-1"]),
      source: "ask",
    }),
  );
  expect(await screen.findByRole("dialog", { name: /send to dsh/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run frontend tests to verify they fail**

Run:

```bash
pnpm --dir integrations/paper-rag-workbench test src/__tests__/components.test.tsx src/__tests__/pages.test.tsx
```

Expected: failures because DSH handoff dialog and page actions do not exist.

- [ ] **Step 3: Implement `DshHandoffDialog`**

Create `DshHandoffDialog.tsx`:

```tsx
import type { DshHandoffData } from "../types";

export function DshHandoffDialog({
  data,
  onClose,
}: {
  data: DshHandoffData;
  onClose: () => void;
}) {
  const copy = async () => {
    await navigator.clipboard?.writeText(data.prompt);
  };

  return (
    <div className="dialog-backdrop">
      <section className="handoff-dialog" role="dialog" aria-label="Send to DSH">
        <header>
          <h3>Send to DSH</h3>
          <button type="button" onClick={onClose} aria-label="Close DSH handoff">
            Close
          </button>
        </header>
        <pre>{data.prompt}</pre>
        <footer>
          <button type="button" onClick={copy}>
            Copy prompt
          </button>
          <a href={data.dsh_url} target="_blank" rel="noreferrer">
            Open DSH
          </a>
        </footer>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Wire handoff actions into pages**

In each page, create state:

```tsx
const [handoff, setHandoff] = useState<DshHandoffData | null>(null);
```

In `AskPage.tsx`, after an answer exists:

```tsx
const sendToDsh = async () => {
  if (!data) return;
  const paperIds = Array.from(new Set(data.chunks.map((chunk) => chunk.paper_id)));
  const chunkIds = data.citations.length ? data.citations : data.chunks.map((chunk) => chunk.chunk_id);
  setHandoff(
    await client.dshHandoff({
      question: question.trim(),
      paper_ids: paperIds,
      chunk_ids: chunkIds,
      source: "ask",
    }),
  );
};
```

Render:

```tsx
<button type="button" onClick={sendToDsh}>
  Send to DSH
</button>
{handoff ? <DshHandoffDialog data={handoff} onClose={() => setHandoff(null)} /> : null}
```

In `SearchPage.tsx`, use the current query and retrieved chunks:

```tsx
const sendSearchToDsh = async () => {
  if (!data) return;
  const results = data.results;
  setHandoff(
    await client.dshHandoff({
      question: query.trim(),
      paper_ids: Array.from(new Set(results.map((chunk) => chunk.paper_id))),
      chunk_ids: results.map((chunk) => chunk.chunk_id),
      source: "search",
    }),
  );
};
```

In `LibraryPage.tsx`, use the selected detail panel:

```tsx
const sendPaperToDsh = async () => {
  if (!detail) return;
  setHandoff(
    await client.dshHandoff({
      question: `继续研究这篇论文：${detail.paper.title}`,
      paper_ids: [detail.paper.paper_id],
      chunk_ids: detail.chunks.slice(0, 8).map((chunk) => chunk.chunk_id),
      source: "library",
    }),
  );
};
```

In `HealthPage.tsx`, use health warnings:

```tsx
const sendHealthToDsh = async () => {
  if (!data) return;
  const warningText = data.warnings.length
    ? data.warnings.join("；")
    : `当前状态：${data.status}`;
  setHandoff(
    await client.dshHandoff({
      question: `诊断这些 Paper RAG 健康信息：${warningText}`,
      paper_ids: [],
      chunk_ids: [],
      source: "health",
    }),
  );
};
```

- [ ] **Step 5: Add dialog styles**

Add to `styles.css`:

```css
.dialog-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: grid;
  place-items: center;
  padding: 24px;
  z-index: 20;
}

.handoff-dialog {
  width: min(760px, 100%);
  max-height: 80vh;
  overflow: auto;
  background: #ffffff;
  border: 1px solid #dde4eb;
  border-radius: 8px;
  padding: 16px;
}

.handoff-dialog header,
.handoff-dialog footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.handoff-dialog pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: #f3f6f9;
  padding: 12px;
  border-radius: 8px;
}
```

- [ ] **Step 6: Run frontend tests**

Run:

```bash
pnpm --dir integrations/paper-rag-workbench test src/__tests__/components.test.tsx src/__tests__/pages.test.tsx
```

Expected: selected frontend tests pass.

- [ ] **Step 7: Commit Task 6**

Run:

```bash
git add integrations/paper-rag-workbench/src/components/DshHandoffDialog.tsx integrations/paper-rag-workbench/src/pages/AskPage.tsx integrations/paper-rag-workbench/src/pages/SearchPage.tsx integrations/paper-rag-workbench/src/pages/LibraryPage.tsx integrations/paper-rag-workbench/src/pages/HealthPage.tsx integrations/paper-rag-workbench/src/styles.css integrations/paper-rag-workbench/src/__tests__/components.test.tsx integrations/paper-rag-workbench/src/__tests__/pages.test.tsx
git commit -m "feat: add structured dsh handoff"
```

---

### Task 7: Fixture Smoke, Docs, And Final Verification

**Files:**
- Modify: `integrations/paper-rag-workbench/tests/workbench.spec.ts`
- Modify: `integrations/paper-rag-workbench/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: all V2 UI flows from Tasks 4-6.
- Produces: fixture Playwright coverage for Overview, Health, Library, Paper Detail, Search, Ask, Citation Drilldown, Discover approval dialog, and DSH handoff prompt.
- Produces: docs that explain Workbench V2 and DSH's remaining role.

- [ ] **Step 1: Inspect existing Playwright tests**

Run:

```bash
find integrations/paper-rag-workbench -maxdepth 3 -type f \( -name '*.spec.ts' -o -name 'playwright.config.ts' \) -print
```

Then open `integrations/paper-rag-workbench/tests/workbench.spec.ts` and `integrations/paper-rag-workbench/playwright.config.ts`.

- [ ] **Step 2: Add fixture smoke assertions**

Replace the existing test body in `integrations/paper-rag-workbench/tests/workbench.spec.ts` with this flow:

```ts
import { expect, test } from "@playwright/test";

test("workbench v2 fixture flow", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();

  await page.getByRole("button", { name: /health/i }).click();
  await expect(page.getByRole("heading", { name: "Health" })).toBeVisible();
  await expect(page.getByText(/Dense retrieval is unavailable/i)).toBeVisible();

  await page.getByRole("button", { name: /library/i }).click();
  await expect(page.getByText(/Self-RAG/)).toBeVisible();
  await page.getByRole("button", { name: /inspect paper self-rag/i }).click();
  await expect(page.getByText(/Abstract/)).toBeVisible();

  await nav.getByRole("button", { name: /^search$/i }).click();
  await page.getByLabel(/search evidence/i).fill("reflection tokens");
  await page.getByRole("button", { name: /^search$/i }).click();
  await page.getByRole("button", { name: /inspect chunk chunk-self-rag-1/i }).click();
  await expect(page.getByText(/critiques its own generations/i)).toBeVisible();

  await nav.getByRole("button", { name: /^ask$/i }).click();
  await page.getByLabel(/question/i).fill("What is Self-RAG?");
  await page.getByRole("button", { name: /^ask$/i }).click();
  await page.getByRole("button", { name: /chunk-self-rag-1/i }).click();
  await expect(page.getByText(/critiques its own generations/i)).toBeVisible();
  await page.getByRole("button", { name: /send to dsh/i }).click();
  await expect(page.getByRole("dialog", { name: /send to dsh/i })).toBeVisible();

  await nav.getByRole("button", { name: /discover/i }).click();
  await page.getByLabel(/topic/i).fill("agentic rag");
  await page.getByRole("button", { name: /discover/i }).click();
  await page.getByLabel(/select candidate 11/i).check();
  await page.getByRole("button", { name: /ingest selected/i }).click();
  await expect(page.getByText(/write indexed paper and chunks/i)).toBeVisible();
});
```

If route buttons collide with form buttons, select the navigation buttons by `nav[aria-label="Workbench navigation"] button`.

- [ ] **Step 3: Update docs**

In `integrations/paper-rag-workbench/README.md`, add a section named `Workbench V2`:

```markdown
## Workbench V2

Workbench is the primary Paper RAG research interface. It covers:

- Health: SQLite, Qdrant, retrieval fallback, LLM credential status, and data-quality samples.
- Library: indexed papers with paper detail, sections, chunks, and parser warnings.
- Search: evidence retrieval with inspectable chunk drilldown.
- Ask: generated answers with citation drilldown and retrieved evidence.
- Discover: candidate discovery with explicit approval before real-library ingest.
- DSH handoff: copy/open a structured prompt in DSH Web for long-form agent work.

DSH remains the chat and trace companion. Workbench does not depend on DeerFlow
or DSH private session internals.
```

In root `README.md`, add one sentence near the Workbench startup instructions:

```markdown
Paper RAG Workbench is the primary local frontend; DSH Web remains available as
the trace/chat companion for long-form agent handoff.
```

- [ ] **Step 4: Run full verification**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_workbench_read_store.py tests/test_workbench_api.py tests/test_coverage_boost.py::test_paper_search_groups_by_paper_and_keeps_best tests/test_coverage_boost.py::test_paper_search_falls_back_to_hybrid_when_dense_is_empty tests/test_mcp_tools.py
pnpm --dir integrations/paper-rag-workbench test
pnpm --dir integrations/paper-rag-workbench build
VITE_WORKBENCH_FIXTURES=1 pnpm --dir integrations/paper-rag-workbench playwright
.venv/bin/python scripts/secret_scan.py
git status --short
```

Expected:

- Backend tests pass.
- Frontend unit tests pass.
- Frontend build passes.
- Fixture Playwright smoke passes.
- Secret scan prints `secret scan: clean`.
- `git status --short` shows only files intentionally changed by Task 7 before the commit.

- [ ] **Step 5: Commit Task 7**

Run:

```bash
git add integrations/paper-rag-workbench/tests integrations/paper-rag-workbench/README.md README.md
git commit -m "test: cover workbench v2 fixture flow"
```

- [ ] **Step 6: Final clean-tree verification**

Run:

```bash
git status --short
```

Expected: no output.

---

## Final Report Template

Use this exact shape when implementation is complete:

```markdown
Implemented Paper RAG Workbench V2.

Commits:
- `<hash>` feat: add workbench read store
- `<hash>` feat: add workbench v2 api endpoints
- `<hash>` feat: add workbench v2 frontend contracts
- `<hash>` feat: add workbench health page
- `<hash>` feat: add paper detail and citation drilldown
- `<hash>` feat: add structured dsh handoff
- `<hash>` test: cover workbench v2 fixture flow

Verification:
- `PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_workbench_read_store.py tests/test_workbench_api.py tests/test_coverage_boost.py::test_paper_search_groups_by_paper_and_keeps_best tests/test_coverage_boost.py::test_paper_search_falls_back_to_hybrid_when_dense_is_empty tests/test_mcp_tools.py`
- `pnpm --dir integrations/paper-rag-workbench test`
- `pnpm --dir integrations/paper-rag-workbench build`
- `VITE_WORKBENCH_FIXTURES=1 pnpm --dir integrations/paper-rag-workbench playwright`
- `.venv/bin/python scripts/secret_scan.py`
- `git status --short`

Go/no-go:
- Go if all verification commands pass and the worktree is clean.
- Blocked if live DSH route prefill is needed, because Workbench must not depend on DSH private session internals.
```

## Inline Execution Goal Prompt

Use this prompt in goal mode after confirming the plan:

```text
按 docs/superpowers/plans/2026-08-15-paper-rag-workbench-v2.md 用 Inline Execution 实现 Paper RAG Workbench V2，逐 Task 执行并在每个 Task 后提交。

要求：
1. 先读取当前 checkout 的真实代码、docs/superpowers/specs/2026-08-15-paper-rag-workbench-v2-design.md 和 docs/superpowers/plans/2026-08-15-paper-rag-workbench-v2.md，不要凭记忆执行。
2. 使用 superpowers:executing-plans，并按 plan 的 Task 顺序推进，不跳过任务。
3. 每个行为改动先写测试或补充验证，再实现，再运行对应验证命令。
4. 保持模型为 deepseek-v4-flash，不要改模型。
5. 不恢复、不创建 integrations/deer-flow/。
6. 不提交 .env、API key、data/index、runtime/session/credentials、DSH sessions、真实 PDF、generated dist、node_modules 或临时 smoke 数据。
7. 不执行真实写入论文库的 live smoke，除非我另行明确批准；Discover 测试只能到 approval dialog 或使用 fixture。
8. Workbench 是主前端；DSH 只作为 chat/trace companion 和 handoff 目标，不依赖 DSH 私有 session internals。
9. 如果遇到需要外部凭据、真实写入、无法获取源码/版本、DSH 私有 API、或需要人工产品取舍的事情，标记 blocked 并说明具体阻塞项。
10. 完成标准：所有 Task 的实现、测试、fixture Playwright smoke、build、secret scan 全部通过；git 工作树干净；提交代码；汇报 commit 列表、验证命令、go/no-go 状态和剩余风险。
```
