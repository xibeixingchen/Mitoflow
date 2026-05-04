"""Knowledge query tools for MitoFlow AI."""

from __future__ import annotations

from typing import Any, Dict

from .knowledge import KnowledgeBase
from .models import EntryPoint, SafetyLevel, ToolDefinition
from .tools import ToolContext, ToolRegistry

_kb: KnowledgeBase | None = None


def _get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def register_knowledge_tools(registry: ToolRegistry) -> None:
    """Register knowledge query tools."""
    registry.register(
        ToolDefinition(
            name="gene_info_lookup",
            description="Look up detailed information about a plant mitochondrial gene: product name, functional category, aliases, splicing type, RNA editing rules.",
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
        gene_info_lookup,
    )
    registry.register(
        ToolDefinition(
            name="search_genes",
            description="Search for mitochondrial genes by name or product keyword. Returns matching genes and their products.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword (gene name or protein product)."}
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        search_genes,
    )
    registry.register(
        ToolDefinition(
            name="list_gene_categories",
            description="List all functional categories of plant mitochondrial genes (e.g. complex I, complex III, ribosomal).",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        list_gene_categories,
    )
    registry.register(
        ToolDefinition(
            name="get_category_genes",
            description="Get all genes in a specific functional category (e.g. core_complex_i, ribosomal, ccm).",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category name (e.g. core_complex_i, ribosomal)."}
                },
                "required": ["category"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        get_category_genes,
    )
    registry.register(
        ToolDefinition(
            name="get_splicing_info",
            description="Get information about trans-splicing and cis-splicing genes in plant mitochondria.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        get_splicing_info,
    )
    registry.register(
        ToolDefinition(
            name="get_editing_info",
            description="Get information about RNA editing in plant mitochondrial genes (stop-gain, start-gain editing).",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        get_editing_info,
    )


def gene_info_lookup(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    kb = _get_kb()
    info = kb.get_gene_info(args["gene_name"])
    if not info.get("product"):
        return {"content": f"Gene '{args['gene_name']}' not found in the knowledge base.", "data": info}
    parts = [f"{info['gene']}: {info.get('product', 'unknown product')}"]
    if info.get("category"):
        parts.append(f"Category: {info['category']}")
    if info.get("aliases"):
        parts.append(f"Aliases: {', '.join(info['aliases'][:10])}")
    if info.get("special_rules"):
        parts.append(f"Special handling: {', '.join(info['special_rules'])}")
    return {"content": "\n".join(parts), "data": info}


def search_genes(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    kb = _get_kb()
    results = kb.search_gene(args["query"])
    if not results:
        return {"content": f"No genes found matching '{args['query']}'.", "data": {"results": []}}
    lines = [f"Found {len(results)} genes matching '{args['query']}':"]
    for r in results[:10]:
        lines.append(f"  {r['gene']}: {r['product']}")
    return {"content": "\n".join(lines), "data": {"results": results}}


def list_gene_categories(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    kb = _get_kb()
    categories = kb.list_categories()
    lines = ["Plant mitochondrial gene categories:"]
    for cat, genes in categories.items():
        lines.append(f"  {cat}: {', '.join(genes[:5])}{'...' if len(genes) > 5 else ''}")
    return {"content": "\n".join(lines), "data": {"categories": categories}}


def get_category_genes(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    kb = _get_kb()
    genes = kb.get_category_genes(args["category"])
    if not genes:
        return {"content": f"Category '{args['category']}' not found.", "data": {"genes": []}}
    return {
        "content": f"Genes in {args['category']}: {', '.join(genes)}",
        "data": {"category": args["category"], "genes": genes},
    }


def get_splicing_info(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    kb = _get_kb()
    info = kb.get_splicing_info()
    lines = ["Splicing information in plant mitochondria:"]
    for key, val in info.items():
        lines.append(f"  {key}: {val}")
    return {"content": "\n".join(lines), "data": info}


def get_editing_info(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    kb = _get_kb()
    info = kb.get_editing_info()
    lines = ["RNA editing information in plant mitochondria:"]
    for key, val in info.items():
        lines.append(f"  {key}: {val}")
    return {"content": "\n".join(lines), "data": info}
