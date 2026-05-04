"""Wiki tools for AI agent knowledge retrieval."""

from __future__ import annotations

from typing import Any, Dict

from ..models import EntryPoint, SafetyLevel, ToolDefinition
from ..tools import ToolContext, ToolRegistry
from .wiki_index import WikiIndex

_WIKI: WikiIndex | None = None


def _get_wiki() -> WikiIndex:
    global _WIKI
    if _WIKI is None:
        _WIKI = WikiIndex()
    return _WIKI


def register_wiki_tools(registry: ToolRegistry) -> None:
    """Register wiki knowledge tools."""
    registry.register(
        ToolDefinition(
            name="wiki_search",
            description="Search the MitoFlow knowledge wiki for topics like RNA editing, CMS, assembly tools, ERC, comparative genomics.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'RNA editing', 'CMS', 'GetOrganelle')."}
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        wiki_search,
    )
    registry.register(
        ToolDefinition(
            name="wiki_get_page",
            description="Get the full content of a specific wiki page by topic name.",
            parameters={
                "type": "object",
                "properties": {
                    "page_name": {"type": "string", "description": "Page name or topic (e.g. 'rna_editing', 'CMS', 'assembly_tools')."}
                },
                "required": ["page_name"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        wiki_get_page,
    )
    registry.register(
        ToolDefinition(
            name="wiki_list_pages",
            description="List all available wiki knowledge pages.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        wiki_list_pages,
    )


def wiki_search(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Search wiki pages."""
    wiki = _get_wiki()
    results = wiki.search(args["query"], limit=5)
    if not results:
        return {"content": f"No wiki pages found for '{args['query']}'.", "data": {"results": []}}
    lines = []
    for r in results:
        refs = ", ".join(r["references"]) if r["references"] else "none"
        lines.append(f"**{r['title']}** (score={r['score']})\n  Tags: {', '.join(r['tags'])}\n  Refs: {refs}\n  {r['summary'][:150]}")
    return {
        "content": "\n\n".join(lines),
        "data": {"results": [{"file": r["file"], "title": r["title"], "score": r["score"]} for r in results]},
    }


def wiki_get_page(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Get full wiki page content."""
    wiki = _get_wiki()
    page = wiki.get_page(args["page_name"])
    if not page:
        # Try search as fallback
        results = wiki.search(args["page_name"], limit=1)
        if results:
            page = results[0]
        else:
            return {"content": f"Page '{args['page_name']}' not found.", "data": {}}
    refs_str = ", ".join(page["references"]) if page["references"] else "none"
    return {
        "content": f"# {page['title']}\n\nReferences: {refs_str}\n\n{page['content']}",
        "data": {"title": page["title"], "tags": page["tags"], "entities": page["entities"]},
    }


def wiki_list_pages(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """List all wiki pages."""
    wiki = _get_wiki()
    pages = wiki.list_pages()
    lines = [f"- **{p['title']}** ({p['file']}) — {', '.join(p['tags'])}" for p in pages]
    return {
        "content": f"Available wiki pages ({len(pages)}):\n" + "\n".join(lines),
        "data": {"pages": pages},
    }
