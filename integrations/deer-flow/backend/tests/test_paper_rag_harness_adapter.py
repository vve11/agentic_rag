from __future__ import annotations


def test_paper_rag_harness_tools_are_importable():
    from deerflow.community.paper_rag import tools

    exposed = {
        tools.paper_qa_tool.name,
        tools.paper_search_tool.name,
        tools.paper_section_tool.name,
        tools.paper_compare_tool.name,
        tools.paper_discover_tool.name,
        tools.wiki_lookup_tool.name,
        tools.export_bibtex_tool.name,
    }

    assert exposed == {
        "paper_qa",
        "paper_search",
        "paper_section",
        "paper_compare",
        "paper_discover",
        "wiki_lookup",
        "export_bibtex",
    }


def test_paper_research_subagent_is_registered():
    from deerflow.subagents.builtins import BUILTIN_SUBAGENTS

    config = BUILTIN_SUBAGENTS["paper-research"]

    assert config.name == "paper-research"
    assert "paper_rag" in config.description
    assert config.tools is not None
    assert "paper_qa" in config.tools
    assert "paper_search" in config.tools
    assert "paper_discover" in config.tools
    assert "wiki_lookup" in config.tools


def test_paper_discover_tool_returns_ranked_candidates(monkeypatch):
    from deerflow.community.paper_rag import tools
    from paper_rag.discovery import runner

    def _fake_run_discovery(topic, *, user_id, source_names=None, max_candidates=10, search_limit=25):
        assert topic == "agentic rag"
        assert user_id == "harness"
        assert max_candidates == 3
        return {
            "run": {"id": 12, "status": "completed", "stopped_by": "selected_limit"},
            "trace": {"trace_id": "disc-123", "loop": [{"stage": "rank", "selected": 1}]},
            "candidates": [
                {
                    "title": "Agentic RAG",
                    "paper_id": "arxiv:2601.00001",
                    "score": 0.81,
                    "selected": True,
                    "rank_reason": "keyword_overlap=0.42; source_confidence=0.15",
                    "skip_reason": None,
                }
            ],
        }

    monkeypatch.setattr(runner, "run_discovery", _fake_run_discovery)

    payload = tools.paper_discover_tool.invoke({"topic": "agentic rag", "max_candidates": 3})

    assert '"trace_id": "disc-123"' in payload
    assert '"paper_id": "arxiv:2601.00001"' in payload
    assert "keyword_overlap" in payload
