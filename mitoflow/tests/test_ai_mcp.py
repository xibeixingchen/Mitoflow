"""Tests for the MCP knowledge system."""

from mitoflow.ai.mcp.knowledge_base import KnowledgeBase
from mitoflow.ai.mcp.mcp_server import MitoFlowMCPServer


def test_knowledge_base_loads():
    kb = KnowledgeBase()
    assert len(kb.db.references) > 0
    assert len(kb.db.entities) > 0


def test_lookup_gene_with_references():
    kb = KnowledgeBase()
    info = kb.lookup_gene("CMS")

    assert info.get("entity") == "CMS"
    assert len(info.get("references", [])) > 0
    assert any(r.get("doi") for r in info["references"])


def test_lookup_tool():
    kb = KnowledgeBase()
    info = kb.lookup_tool("GetOrganelle")

    assert info.get("tool") == "GetOrganelle"
    assert len(info.get("references", [])) > 0
    assert info["references"][0].get("doi") is not None


def test_search_literature():
    kb = KnowledgeBase()
    results = kb.search_literature("RNA editing")

    assert len(results) > 0
    assert any("RNA" in r["title"] for r in results)


def test_get_assembly_tools():
    kb = KnowledgeBase()
    tools = kb.get_assembly_tools()

    assert len(tools) >= 3
    names = [t["title"] for t in tools]
    assert any("GetOrganelle" in n for n in names)


def test_format_response_with_citations():
    kb = KnowledgeBase()
    response = kb.format_response_with_citations("concept", "CMS")

    assert "CMS" in response
    assert "DOI:" in response


def test_mcp_server_tools():
    server = MitoFlowMCPServer()
    tools = server.get_tools()

    assert len(tools) >= 5
    names = [t["name"] for t in tools]
    assert "lookup_gene_with_references" in names
    assert "search_literature" in names


def test_mcp_server_call_tool():
    server = MitoFlowMCPServer()
    result = server.call_tool("lookup_gene_with_references", {"gene_name": "cox1"})

    assert "content" in result
    assert len(result["content"]) > 0


def test_mcp_server_search():
    server = MitoFlowMCPServer()
    result = server.call_tool("search_literature", {"query": "assembly"})

    assert "Found" in result["content"]
    assert result["data"]["count"] > 0
