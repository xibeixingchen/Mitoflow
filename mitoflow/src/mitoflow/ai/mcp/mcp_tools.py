"""MCP-based tools registered in the MitoFlow AI agent system."""

from __future__ import annotations

from typing import Any, Dict

from ..models import EntryPoint, SafetyLevel, ToolDefinition
from ..tools import ToolContext, ToolRegistry
from .knowledge_base import KnowledgeBase
from .mcp_server import MitoFlowMCPServer

_mcp_server: MitoFlowMCPServer | None = None


def _get_mcp() -> MitoFlowMCPServer:
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MitoFlowMCPServer()
    return _mcp_server


def register_mcp_tools(registry: ToolRegistry) -> None:
    """Register MCP knowledge tools in the agent registry."""
    registry.register(
        ToolDefinition(
            name="lookup_gene_with_references",
            description="Look up a plant mitochondrial gene with function, product, category, and literature references (DOIs). Always cite sources.",
            parameters={
                "type": "object",
                "properties": {
                    "gene_name": {"type": "string", "description": "Gene name (e.g. cox1, atp6, nad1)."}
                },
                "required": ["gene_name"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        _lookup_gene,
    )
    registry.register(
        ToolDefinition(
            name="lookup_tool_with_references",
            description="Look up a bioinformatics tool with description, capabilities, and original publication (DOI).",
            parameters={
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "Tool name (e.g. GetOrganelle, IQ-TREE)."}
                },
                "required": ["tool_name"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        _lookup_tool,
    )
    registry.register(
        ToolDefinition(
            name="search_literature",
            description="Search plant organelle genomics literature. Returns papers with DOIs, key findings.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword (e.g. 'RNA editing', 'CMS')."},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        _search_literature,
    )
    registry.register(
        ToolDefinition(
            name="get_assembly_tools",
            description="List all organelle genome assembly tools with publications.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        _get_assembly_tools,
    )
    registry.register(
        ToolDefinition(
            name="get_concept_info",
            description="Get info about a concept in plant organelle genomics (CMS, RNA editing, ERC) with references.",
            parameters={
                "type": "object",
                "properties": {
                    "concept": {"type": "string", "description": "Concept name (e.g. CMS, RNA editing, ERC)."}
                },
                "required": ["concept"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        _get_concept_info,
    )


def _lookup_gene(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    mcp = _get_mcp()
    result = mcp.call_tool("lookup_gene_with_references", args)
    return {"content": result.get("content", ""), "data": result.get("data", {})}


def _lookup_tool(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    mcp = _get_mcp()
    result = mcp.call_tool("lookup_tool_with_references", args)
    return {"content": result.get("content", ""), "data": result.get("data", {})}


def _search_literature(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    mcp = _get_mcp()
    result = mcp.call_tool("search_literature", args)
    return {"content": result.get("content", ""), "data": result.get("data", {})}


def _get_assembly_tools(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    mcp = _get_mcp()
    result = mcp.call_tool("get_assembly_tools", args)
    return {"content": result.get("content", ""), "data": result.get("data", {})}


def _get_concept_info(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    mcp = _get_mcp()
    result = mcp.call_tool("get_concept_info", args)
    return {"content": result.get("content", ""), "data": result.get("data", {})}
