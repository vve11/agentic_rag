from __future__ import annotations


def test_paper_rag_harness_tools_are_importable():
    from deerflow.community.paper_rag import tools

    exposed = {
        tools.paper_qa_tool.name,
        tools.paper_search_tool.name,
        tools.paper_section_tool.name,
        tools.paper_compare_tool.name,
        tools.wiki_lookup_tool.name,
        tools.export_bibtex_tool.name,
    }

    assert exposed == {
        "paper_qa",
        "paper_search",
        "paper_section",
        "paper_compare",
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
    assert "wiki_lookup" in config.tools
