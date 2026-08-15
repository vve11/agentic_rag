from __future__ import annotations

from pathlib import Path


def test_workspace_store_creates_updates_archives_project(tmp_path: Path):
    from paper_rag.workbench.workspace_store import WorkspaceStore

    store = WorkspaceStore(tmp_path / "state.sqlite")

    project = store.create_project("Self-RAG 调研", "evidence-first project")
    updated = store.update_project(
        project["project_id"],
        name="Self-RAG 深入调研",
        description="updated",
    )
    archived = store.archive_project(project["project_id"])

    assert project["status"] == "active"
    assert updated["name"] == "Self-RAG 深入调研"
    assert updated["description"] == "updated"
    assert archived["status"] == "archived"
    assert store.list_projects() == []
    assert store.list_projects(include_archived=True)[0]["project_id"] == project["project_id"]


def test_workspace_store_saves_papers_evidence_notes_and_questions(tmp_path: Path):
    from paper_rag.workbench.workspace_store import WorkspaceStore

    store = WorkspaceStore(tmp_path / "state.sqlite")
    project = store.create_project("Self-RAG 调研")

    paper = store.add_project_paper(
        project["project_id"],
        "arxiv:2310.11511",
        title_snapshot="Self-RAG",
        source="library",
    )
    duplicate = store.add_project_paper(
        project["project_id"],
        "arxiv:2310.11511",
        title_snapshot="Self-RAG duplicate",
        source="search",
    )
    pin = store.pin_evidence(
        project["project_id"],
        "chunk-self-rag-1",
        "arxiv:2310.11511",
        quote_snapshot="SELF-RAG retrieves passages on demand.",
        source="search",
        score_snapshot=0.92,
        label="method",
    )
    note = store.upsert_note(
        project["project_id"],
        "chunk",
        "chunk-self-rag-1",
        "This is my reading note, not paper evidence.",
    )
    saved = store.save_question(
        project["project_id"],
        "What is Self-RAG?",
        "Self-RAG decides when to retrieve.",
        ["chunk-self-rag-1"],
        ["chunk-self-rag-1"],
        trace_id="trace-workbench-fixture",
        abstain={"decision": "answer"},
    )
    snapshot = store.build_project_snapshot(project["project_id"])

    assert paper["paper_id"] == duplicate["paper_id"]
    assert pin["chunk_id"] == "chunk-self-rag-1"
    assert note["target_type"] == "chunk"
    assert saved["citations"] == ["chunk-self-rag-1"]
    assert snapshot["summary"] == {
        "paper_count": 1,
        "evidence_count": 1,
        "note_count": 1,
        "saved_question_count": 1,
        "compare_run_count": 0,
    }


def test_workspace_store_dsh_handoff_prompt_is_secret_safe(tmp_path: Path):
    from paper_rag.workbench.workspace_store import WorkspaceStore

    store = WorkspaceStore(tmp_path / "state.sqlite")
    project = store.create_project("Self-RAG 调研", "project description")
    store.add_project_paper(project["project_id"], "arxiv:2310.11511", "Self-RAG", "library")
    store.pin_evidence(
        project["project_id"],
        "chunk-self-rag-1",
        "arxiv:2310.11511",
        quote_snapshot="evidence excerpt",
        source="ask",
    )
    store.upsert_note(project["project_id"], "project", project["project_id"], "local note")

    handoff = store.create_dsh_handoff(project["project_id"], "Compare methods.")

    assert "Self-RAG 调研" in handoff["prompt"]
    assert "chunk-self-rag-1" in handoff["prompt"]
    assert "local note" in handoff["prompt"]
    assert "sk-" not in handoff["prompt"]
    assert ".credentials" not in handoff["prompt"]
