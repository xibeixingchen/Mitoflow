"""MCP server for MitoFlow knowledge system."""

from __future__ import annotations

from typing import Any, Dict, List

from .knowledge_base import KnowledgeBase


class MitoFlowMCPServer:
    """MCP server providing knowledge-grounded tools for plant organelle genomics.

    This server exposes tools that return information with literature citations,
    ensuring all answers are traceable to published sources.
    """

    def __init__(self, knowledge_base: KnowledgeBase | None = None) -> None:
        self.kb = knowledge_base or KnowledgeBase()

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return MCP tool definitions."""
        return [
            {
                "name": "lookup_gene_with_references",
                "description": (
                    "Look up a plant mitochondrial gene and get its function, "
                    "product name, functional category, and literature references with DOIs."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "gene_name": {
                            "type": "string",
                            "description": "Gene name (e.g. cox1, atp6, nad1)",
                        }
                    },
                    "required": ["gene_name"],
                },
            },
            {
                "name": "lookup_tool_with_references",
                "description": (
                    "Look up a bioinformatics tool and get its description, "
                    "capabilities, and the original publication with DOI."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "Tool name (e.g. GetOrganelle, IQ-TREE, OrthoFinder)",
                        }
                    },
                    "required": ["tool_name"],
                },
            },
            {
                "name": "search_literature",
                "description": (
                    "Search the plant organelle genomics literature database. "
                    "Returns papers with DOIs, key findings, and related entities."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword (e.g. 'RNA editing', 'CMS', 'assembly')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_assembly_tools",
                "description": (
                    "List all available organelle genome assembly tools "
                    "with their descriptions and original publications."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_concept_info",
                "description": (
                    "Get detailed information about a concept in plant organelle genomics "
                    "(e.g. CMS, RNA editing, ERC) with literature references."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "Concept name (e.g. CMS, RNA editing, ERC)",
                        }
                    },
                    "required": ["concept"],
                },
            },
            {
                "name": "list_all_tools",
                "description": "List all integrated bioinformatics tools with their descriptions and references.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        if name == "lookup_gene_with_references":
            return self._lookup_gene(arguments)
        elif name == "lookup_tool_with_references":
            return self._lookup_tool(arguments)
        elif name == "search_literature":
            return self._search_literature(arguments)
        elif name == "get_assembly_tools":
            return self._get_assembly_tools()
        elif name == "get_concept_info":
            return self._get_concept_info(arguments)
        elif name == "list_all_tools":
            return self._list_all_tools()
        else:
            return {"error": f"Unknown tool: {name}"}

    def _lookup_gene(self, args: Dict[str, Any]) -> Dict[str, Any]:
        gene_name = args.get("gene_name", "")
        info = self.kb.lookup_gene(gene_name)
        formatted = self.kb.format_response_with_citations("gene", gene_name)
        return {"content": formatted, "data": info}

    def _lookup_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = args.get("tool_name", "")
        info = self.kb.lookup_tool(tool_name)
        formatted = self.kb.format_response_with_citations("tool", tool_name)
        return {"content": formatted, "data": info}

    def _search_literature(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        limit = args.get("limit", 10)
        results = self.kb.search_literature(query, limit)
        lines = [f"Found {len(results)} papers matching '{query}':"]
        for ref in results:
            lines.append(f"  [{ref['id']}] {ref['citation']}")
            lines.append(f"    {ref['title']}")
            if ref.get("key_findings"):
                lines.append(f"    Key: {ref['key_findings'][0]}")
        return {"content": "\n".join(lines), "data": {"results": results, "count": len(results)}}

    def _get_assembly_tools(self) -> Dict[str, Any]:
        tools = self.kb.get_assembly_tools()
        lines = ["Organelle genome assembly tools:"]
        for tool in tools:
            lines.append(f"  {tool['title']}")
            lines.append(f"    {tool['citation']}")
        return {"content": "\n".join(lines), "data": {"tools": tools}}

    def _get_concept_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        concept = args.get("concept", "")
        info = self.kb.get_concept_info(concept)
        formatted = self.kb.format_response_with_citations("concept", concept)
        return {"content": formatted, "data": info}

    def _list_all_tools(self) -> Dict[str, Any]:
        tools = self.kb.get_all_tools()
        lines = ["Integrated bioinformatics tools:"]
        for tool in tools:
            refs = ", ".join(tool.get("references", []))
            lines.append(f"  {tool['tool']}: {tool['description']}")
            if refs:
                lines.append(f"    Refs: {refs}")
        return {"content": "\n".join(lines), "data": {"tools": tools}}
