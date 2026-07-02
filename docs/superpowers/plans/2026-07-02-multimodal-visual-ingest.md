# Multimodal Visual Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich MinerU-extracted figure/table chunks with vision-model summaries before SQLite/Qdrant indexing, using an OpenAI-compatible API first and a lazy Qwen2.5-VL local fallback.

**Architecture:** Add a focused `paper_rag.vision` package with schema, cache, API adapter, local adapter, and enrichment orchestration. `chunk.builder` remains the only integration point: it creates text/figure/table/formula chunks as today, then calls vision enrichment for visual chunks before returning them to the ingest pipeline.

**Tech Stack:** Python 3.10+, Pydantic config, OpenAI Python client, base64 data URLs, SQLite/Qdrant existing payloads, pytest, ReportLab course PDF generator.

---

## File Structure

- Create `src/paper_rag/vision/__init__.py`: package exports.
- Create `src/paper_rag/vision/schema.py`: request/result dataclasses and status constants.
- Create `src/paper_rag/vision/cache.py`: JSON cache keyed by image bytes, context, model, and prompt version.
- Create `src/paper_rag/vision/api.py`: OpenAI-compatible vision adapter.
- Create `src/paper_rag/vision/local.py`: lazy Qwen2.5-VL fallback adapter that returns unavailable when dependencies are missing.
- Create `src/paper_rag/vision/enrich.py`: enrich visual chunks and append summaries to `text` / `context_text`.
- Modify `src/paper_rag/config.py`: add `_Vision` config model and expose it on `AppConfig`.
- Modify `config/default.yaml`, `config/local.yaml`, `config/production.yaml`: add `vision` defaults.
- Modify `src/paper_rag/chunk/builder.py`: call `vision.enrich.enrich_chunks()` after chunk construction.
- Modify `tests/test_pure.py`: assert visual enrichment in build_chunks using a fake summarizer.
- Create `tests/test_vision.py`: unit tests for cache, API success/failure, local fallback unavailable, limits.
- Modify `README.md`, `README_EN.md`, `docs/MINERU_SETUP.md`, `docs/OPERATIONS.md`, `course/paper_rag_agent_project_manual.md`: document setup and behavior.
- Regenerate `course/paper_rag_agent_project_manual.pdf` with `scripts/generate_course_pdf.py`.

## Task 1: Config and Vision Schema

**Files:**
- Modify: `src/paper_rag/config.py`
- Modify: `config/default.yaml`
- Modify: `config/local.yaml`
- Modify: `config/production.yaml`
- Create: `src/paper_rag/vision/__init__.py`
- Create: `src/paper_rag/vision/schema.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: Write failing config/schema tests**

Add tests that load a temporary config with a `vision` block and instantiate a `VisualSummaryRequest`:

```python
def test_vision_config_defaults_exist():
    from paper_rag import config as cfg

    c = cfg.load()
    assert c.vision.provider == "openai_compatible"
    assert c.vision.max_images_per_paper >= 1


def test_visual_summary_request_schema(tmp_path):
    from paper_rag.vision.schema import VisualSummaryRequest

    image = tmp_path / "fig.png"
    image.write_bytes(b"fake")
    req = VisualSummaryRequest(
        paper_id="p1",
        chunk_id="c1",
        modality="figure",
        asset_path=image,
        caption="Pipeline",
        surrounding_context="The method has three stages.",
    )
    assert req.asset_path == image
    assert req.prompt_version == "v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_vision.py::test_vision_config_defaults_exist tests/test_vision.py::test_visual_summary_request_schema
```

Expected: FAIL because `paper_rag.vision` and `AppConfig.vision` do not exist.

- [ ] **Step 3: Implement config and schema**

Add `_Vision` to `config.py`:

```python
class _Vision(BaseModel):
    enabled: bool = False
    provider: str = "openai_compatible"
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_sec: int = 60
    fallback_local: bool = False
    local_model: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    max_images_per_paper: int = 40
    max_image_bytes: int = 8_000_000
    cache: bool = True
    cache_dir: str = "./data/index/vision_cache"
```

Expose it:

```python
class AppConfig(BaseModel):
    ...
    vision: _Vision = Field(default_factory=_Vision)
```

Create `schema.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATUS_OK = "ok"
STATUS_FALLBACK = "fallback"
STATUS_CACHED = "cached"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"
STATUS_UNAVAILABLE = "unavailable"
PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class VisualSummaryRequest:
    paper_id: str
    chunk_id: str
    modality: str
    asset_path: Path
    caption: str = ""
    surrounding_context: str = ""
    model: str | None = None
    prompt_version: str = PROMPT_VERSION


@dataclass
class VisualSummaryResult:
    status: str
    summary: str = ""
    provider: str | None = None
    model: str | None = None
    raw: dict[str, Any] | None = None
    error: str | None = None
    cache_key: str | None = None
    warnings: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Add YAML defaults**

Add `vision` blocks to all configs. Defaults must not break current installs:

```yaml
vision:
  enabled: false
  provider: openai_compatible
  base_url: $VISION_BASE_URL
  api_key: $VISION_API_KEY
  model: $VISION_MODEL
  timeout_sec: 60
  fallback_local: false
  local_model: Qwen/Qwen2.5-VL-7B-Instruct
  max_images_per_paper: 40
  max_image_bytes: 8000000
  cache: true
  cache_dir: ./data/index/vision_cache
```

- [ ] **Step 5: Run tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_vision.py::test_vision_config_defaults_exist tests/test_vision.py::test_visual_summary_request_schema
```

Expected: PASS.

## Task 2: Cache and API Adapter

**Files:**
- Create: `src/paper_rag/vision/cache.py`
- Create: `src/paper_rag/vision/api.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: Write failing cache/API tests**

Tests should assert deterministic cache keys, cache round trip, and API adapter message shape with a fake OpenAI client:

```python
def test_cache_round_trip(tmp_path):
    from paper_rag.vision.cache import VisionSummaryCache
    from paper_rag.vision.schema import VisualSummaryRequest, VisualSummaryResult

    image = tmp_path / "fig.png"
    image.write_bytes(b"image")
    cache = VisionSummaryCache(tmp_path / "cache")
    req = VisualSummaryRequest("p1", "c1", "figure", image, "caption", "context", model="m")
    key = cache.key_for(req)
    cache.write(key, VisualSummaryResult(status="ok", summary="summary", provider="api", model="m"))
    assert cache.read(key).summary == "summary"


def test_api_adapter_success(tmp_path, monkeypatch):
    from paper_rag.vision.api import OpenAIVisionSummarizer
    from paper_rag.vision.schema import VisualSummaryRequest

    image = tmp_path / "fig.png"
    image.write_bytes(b"image")
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            msg = type("Msg", (), {"content": '{"main_message":"A pipeline diagram"}'})
            choice = type("Choice", (), {"message": msg})
            return type("Resp", (), {"choices": [choice]})

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    adapter = OpenAIVisionSummarizer(
        base_url="https://vision.example.test",
        api_key="test",
        model="vision-model",
        client_factory=lambda: FakeClient(),
    )
    out = adapter.summarize(VisualSummaryRequest("p1", "c1", "figure", image))
    assert out.status == "ok"
    assert "pipeline" in out.summary.lower()
    assert calls[0]["model"] == "vision-model"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_vision.py::test_cache_round_trip tests/test_vision.py::test_api_adapter_success
```

Expected: FAIL because cache/API modules do not exist.

- [ ] **Step 3: Implement cache**

Use JSON files under `cache_dir`, one file per SHA-256 key. Include image bytes, caption, context, model, and prompt version in the key.

- [ ] **Step 4: Implement API adapter**

Use the OpenAI client with image content:

```python
messages = [{
    "role": "user",
    "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_url}},
    ],
}]
```

Parse JSON when possible; otherwise store plain text. Return `VisualSummaryResult(status="ok", provider="api", ...)` on success and `status="failed"` on recoverable API errors.

- [ ] **Step 5: Run tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_vision.py::test_cache_round_trip tests/test_vision.py::test_api_adapter_success
```

Expected: PASS.

## Task 3: Local Fallback and Enrichment Orchestrator

**Files:**
- Create: `src/paper_rag/vision/local.py`
- Create: `src/paper_rag/vision/enrich.py`
- Test: `tests/test_vision.py`

- [ ] **Step 1: Write failing enrichment tests**

Add tests for API success, cache hit, fallback success, all-failed behavior, and per-paper limit:

```python
def test_enrich_chunks_appends_visual_summary(tmp_path):
    from paper_rag.vision.enrich import enrich_chunks
    from paper_rag.vision.schema import VisualSummaryResult

    image = tmp_path / "fig.png"
    image.write_bytes(b"image")
    chunks = [{
        "chunk_id": "c1",
        "paper_id": "p1",
        "modality": "figure",
        "text": "Figure: pipeline\nContext: before after\nPath: figures/fig.png",
        "context_text": "Figure: pipeline",
        "asset_path": str(image),
        "metadata": {"element_type": "figure"},
    }]
    out = enrich_chunks(
        "p1",
        chunks,
        summarizer=lambda req: VisualSummaryResult(status="ok", summary="Shows a three-stage pipeline.", provider="api", model="m"),
    )
    assert "Visual summary: Shows a three-stage pipeline." in out[0]["text"]
    assert out[0]["metadata"]["visual_summary_status"] == "ok"


def test_enrich_chunks_all_failures_keep_ingest_text(tmp_path):
    from paper_rag.vision.enrich import enrich_chunks
    from paper_rag.vision.schema import VisualSummaryResult

    image = tmp_path / "fig.png"
    image.write_bytes(b"image")
    chunk = {"chunk_id": "c1", "paper_id": "p1", "modality": "figure", "text": "original", "context_text": "original", "asset_path": str(image), "metadata": {}}
    out = enrich_chunks("p1", [chunk], summarizer=lambda req: VisualSummaryResult(status="failed", error="boom"))
    assert out[0]["text"] == "original"
    assert out[0]["metadata"]["visual_summary_status"] == "failed"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_vision.py::test_enrich_chunks_appends_visual_summary tests/test_vision.py::test_enrich_chunks_all_failures_keep_ingest_text
```

Expected: FAIL because enrichment module does not exist.

- [ ] **Step 3: Implement local fallback**

`local.py` should lazy-import local dependencies and return `status="unavailable"` when missing:

```python
class LocalVisionSummarizer:
    def summarize(self, request: VisualSummaryRequest) -> VisualSummaryResult:
        try:
            import torch
            from PIL import Image
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        except Exception as exc:
            return VisualSummaryResult(status="unavailable", provider="local", model=self.model, error=str(exc))
```

The first implementation can keep actual inference narrow but functional for prepared Qwen2.5-VL environments.

- [ ] **Step 4: Implement enrichment**

`enrich_chunks()` should:

- Skip non-visual chunks.
- Skip missing/oversized assets.
- Use cache before summarizer calls.
- Call API summarizer first through an injected callable or default factory.
- Try local fallback when API fails and fallback is enabled.
- Append `Visual summary: ...` to both `text` and `context_text` only on successful/cached/fallback summaries.
- Always write metadata status/provider/model/error/cache key.

- [ ] **Step 5: Run enrichment tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_vision.py
```

Expected: PASS.

## Task 4: Integrate Enrichment into Chunk Builder

**Files:**
- Modify: `src/paper_rag/chunk/builder.py`
- Modify: `tests/test_pure.py`
- Test: `tests/test_pure.py`

- [ ] **Step 1: Write failing builder integration test**

Add a test that monkeypatches `paper_rag.vision.enrich.enrich_chunks` and asserts `build_chunks()` returns the enriched text:

```python
def test_build_chunks_calls_visual_enrichment(tmp_path: Path, monkeypatch):
    from paper_rag.chunk import builder

    parsed = tmp_path / "parsed"
    figures = parsed / "figures"
    figures.mkdir(parents=True)
    (figures / "a.png").write_bytes(b"fake")
    (parsed / "paper.md").write_text("# Method\n![pipeline](figures/a.png)\n", encoding="utf-8")

    def fake_enrich(paper_id, chunks):
        for chunk in chunks:
            if chunk.get("modality") == "figure":
                chunk["text"] += "\nVisual summary: mocked"
                chunk["context_text"] += "\nVisual summary: mocked"
                chunk.setdefault("metadata", {})["visual_summary_status"] = "ok"
        return chunks

    monkeypatch.setattr("paper_rag.vision.enrich.enrich_chunks", fake_enrich)
    _, chunks = builder.build_chunks("p1", parsed, title="Paper")
    fig = next(c for c in chunks if c["modality"] == "figure")
    assert "Visual summary: mocked" in fig["text"]
```

- [ ] **Step 2: Run failing test**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_pure.py::test_build_chunks_calls_visual_enrichment
```

Expected: FAIL because `build_chunks()` does not call enrichment.

- [ ] **Step 3: Modify builder**

Import lazily at the end of `build_chunks()`:

```python
try:
    from paper_rag.vision.enrich import enrich_chunks
    chunks = enrich_chunks(paper_id, chunks)
except Exception as exc:
    log.warning(f"visual enrichment skipped: {exc}")
```

This must not block ingestion.

- [ ] **Step 4: Run pure tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_pure.py tests/test_vision.py tests/test_retrieve_pure.py
```

Expected: PASS.

## Task 5: Documentation and Course Material

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `docs/MINERU_SETUP.md`
- Modify: `docs/OPERATIONS.md`
- Modify: `course/paper_rag_agent_project_manual.md`
- Modify: `course/paper_rag_agent_project_manual.pdf`

- [ ] **Step 1: Update README files**

Document:

- `vision.enabled`
- `VISION_BASE_URL`, `VISION_API_KEY`, `VISION_MODEL`
- API-first behavior
- local Qwen2.5-VL fallback
- failure-safe ingest behavior
- how visual summaries improve figure/table retrieval

- [ ] **Step 2: Update MinerU and operations docs**

Add a section explaining that MinerU produces assets and vision summarization enriches them before embedding. Include troubleshooting for missing image assets, API errors, and local fallback unavailable.

- [ ] **Step 3: Update course manual Markdown**

Add a student-facing explanation under the data ingest/chunk sections:

```text
MinerU 不只是抽文本；它还能把图像资产落到 figures/。项目新增的 vision enrichment 会用 API 多模态模型读取图表，并把 caption、上下文和视觉摘要合并为可检索 chunk。
```

- [ ] **Step 4: Regenerate course PDF**

Run:

```bash
.venv/bin/python scripts/generate_course_pdf.py
```

Expected: `course/paper_rag_agent_project_manual.pdf` updates successfully.

## Task 6: Verification and Commit

**Files:**
- All changed files

- [ ] **Step 1: Run targeted tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_vision.py tests/test_pure.py tests/test_retrieve_pure.py
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched Python files**

Run:

```bash
.venv/bin/ruff check src/paper_rag/vision src/paper_rag/config.py src/paper_rag/chunk/builder.py tests/test_vision.py tests/test_pure.py
```

Expected: PASS.

- [ ] **Step 3: Run smoke and secret scan**

Run:

```bash
PYTHONPATH=src .venv/bin/python scripts/_run_smoke.py
.venv/bin/python scripts/secret_scan.py
```

Expected: smoke reports all modules importable; secret scan clean.

- [ ] **Step 4: Commit and push**

Run:

```bash
git add src/paper_rag/vision src/paper_rag/config.py src/paper_rag/chunk/builder.py config/default.yaml config/local.yaml config/production.yaml tests/test_vision.py tests/test_pure.py README.md README_EN.md docs/MINERU_SETUP.md docs/OPERATIONS.md course/paper_rag_agent_project_manual.md course/paper_rag_agent_project_manual.pdf
git commit -m "Add multimodal visual ingest enrichment"
git push origin HEAD:main
```

Expected: remote `main` advances to the new commit and working tree is clean.

## Self-Review

- Spec coverage: API-first summarizer, local Qwen2.5-VL fallback, cache, limits, failure-safe ingest, metadata storage, retrieval compatibility, docs, and course PDF are all covered.
- Placeholder scan: no unresolved markers or open-ended implementation placeholders are intentionally left in this plan.
- Type consistency: `VisualSummaryRequest`, `VisualSummaryResult`, `vision` config keys, and `visual_summary_status` names match the approved design.
