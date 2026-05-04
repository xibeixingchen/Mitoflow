"""Web-aware tools — literature search, GitHub lookup, with citation formatting."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from urllib.request import Request, urlopen
from urllib.error import URLError
from .models import EntryPoint, SafetyLevel, ToolDefinition
from .tools import ToolContext, ToolRegistry


def register_web_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="web_search_literature",
            description=(
                "Search for scientific literature about a topic in plant organelle genomics. "
                "Returns papers with DOI links. Use this for finding references on specific genes, "
                "methods, or concepts. Prioritizes peer-reviewed literature."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'cox1 RNA editing plant mitochondria')"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Max number of results (default 5)"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.EXTERNAL_NETWORK,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        web_search_literature,
    )
    registry.register(
        ToolDefinition(
            name="web_lookup_github",
            description=(
                "Look up a bioinformatics tool on GitHub. Returns repository description, "
                "stars, and URL. Use this when the tool is not in the local literature database."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "GitHub repository (e.g. 'Kinggerm/GetOrganelle' or just tool name)"},
                },
                "required": ["repo"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.EXTERNAL_NETWORK,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        web_lookup_github,
    )
    registry.register(
        ToolDefinition(
            name="web_fetch_page",
            description=(
                "Fetch and extract text content from a URL. Use to read documentation, "
                "papers, or any web page. Returns extracted text content."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to fetch (e.g. https://doi.org/10.1093/nar/gkz940)"},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.EXTERNAL_NETWORK,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        web_fetch_page,
    )


def _http_get(url: str, timeout: int = 10) -> str | None:
    """Simple HTTP GET with timeout. Returns body text or None."""
    try:
        req = Request(url, headers={"User-Agent": "MitoFlow-AI/1.0 (academic)", "Accept": "text/html,application/json"})
        resp = urlopen(req, timeout=timeout)
        # Follow redirects manually if needed
        body = resp.read().decode("utf-8", errors="replace")
        return body[:50000]  # limit to 50KB
    except Exception:
        return None


def _extract_text(html: str) -> str:
    """Crude HTML text extractor."""
    # Remove scripts and styles
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:3000]


def web_search_literature(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Search literature — first local refs, then CrossRef API."""
    query = args["query"]
    max_results = args.get("max_results", 5)

    # 1. Search local reference database first
    from .mcp.references_schema import ReferenceDatabase
    db = ReferenceDatabase()
    local_results = db.search(query)

    results: List[Dict[str, str]] = []
    for ref in local_results[:max_results]:
        results.append({
            "title": ref.title,
            "authors": ", ".join(ref.authors[:3]) + (" et al." if len(ref.authors) > 3 else ""),
            "journal": ref.journal,
            "year": str(ref.year),
            "doi": ref.doi,
            "link": f"[{ref.doi}](https://doi.org/{ref.doi}) `accessible`" if ref.doi else "",
            "source": "local",
        })

    # 2. If not enough local results, try CrossRef API
    if len(results) < max_results:
        try:
            crossref_url = f"https://api.crossref.org/works?query={query}&rows={max_results - len(results)}&filter=type:journal-article"
            body = _http_get(crossref_url, timeout=8)
            if body:
                data = json.loads(body)
                items = data.get("message", {}).get("items", [])
                for item in items:
                    doi = item.get("DOI", "")
                    title = item.get("title", [""])[0]
                    authors = [a.get("given", "") + " " + a.get("family", "") for a in item.get("author", [])[:3]]
                    journal = item.get("container-title", [""])[0] if item.get("container-title") else ""
                    year = str(item.get("created", {}).get("date-parts", [[0]])[0][0])
                    results.append({
                        "title": title,
                        "authors": ", ".join(authors) + (" et al." if len(item.get("author", [])) > 3 else ""),
                        "journal": journal,
                        "year": year,
                        "doi": doi,
                        "link": f"[{doi}](https://doi.org/{doi}) `accessible`" if doi else "",
                        "source": "crossref",
                    })
        except Exception:
            pass

    # 3. Format output
    if not results:
        content = f"No literature found for '{query}'. Try broader search terms."
    else:
        lines = [f"Literature results for '{query}':", ""]
        for i, r in enumerate(results[:max_results], 1):
            lines.append(f"{i}. **{r['title']}**")
            lines.append(f"   {r['authors']} ({r['year']}) *{r['journal']}*")
            if r.get("link"):
                lines.append(f"   {r['link']}")
            lines.append("")
        content = "\n".join(lines)

    return {"content": content, "data": {"results": results[:max_results]}}


def web_lookup_github(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Look up a tool on GitHub via the GitHub API."""
    repo = args["repo"].strip()

    # Auto-detect common tool repos
    KNOWN_REPOS = {
        "getorganelle": "Kinggerm/GetOrganelle",
        "novoplasty": "ndierckxsens/NOVOPlasty",
        "mitobim": "chrishah/MITObim",
        "pga": "quxiaojian/PGA",
        "orthofinder": "davidemms/OrthoFinder",
        "iqtree": "iqtree/iqtree2",
        "iq-tree": "iqtree/iqtree2",
        "iqtree2": "iqtree/iqtree2",
        "mafft": "GSLBiotech/MAFFT",
        "trimal": "inab/trimal",
        "busco": "busco/BUSCO",
        "ercnet2": "",
        "mitofflow": "xibeixingchen/MitoFlow",
    }

    repo_path = KNOWN_REPOS.get(repo.lower(), repo)
    if "/" not in repo_path:
        content = f"Could not identify GitHub repository for '{repo}'. Try providing the full name (e.g. 'Kinggerm/GetOrganelle')."
        return {"content": content, "data": {}}

    # Try GitHub API
    try:
        api_url = f"https://api.github.com/repos/{repo_path}"
        body = _http_get(api_url, timeout=8)
        if body:
            data = json.loads(body)
            content = (
                f"**{data.get('full_name', repo_path)}**\n"
                f"⭐ {data.get('stargazers_count', '?')} stars | 🍴 {data.get('forks_count', '?')} forks\n"
                f"📝 {data.get('description', 'No description')}\n"
                f"🔗 [{data.get('html_url', '')}]({data.get('html_url', '')}) `accessible`\n"
                f"📅 Updated: {data.get('updated_at', '')[:10]} | Language: {data.get('language', '?')}"
            )
            return {"content": content, "data": data}
    except Exception:
        pass

    # Fallback: return constructed URL
    github_url = f"https://github.com/{repo_path}"
    content = (
        f"**{repo_path}**\n"
        f"🔗 [{github_url}]({github_url}) `accessible`\n"
        f"(GitHub API unavailable — showing repository link)"
    )
    return {"content": content, "data": {"url": github_url}}


def web_fetch_page(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Fetch a web page and extract text content."""
    url = args["url"]
    body = _http_get(url, timeout=12)
    if not body:
        return {"content": f"Could not fetch {url}. The page may be unavailable.", "data": {}}

    text = _extract_text(body)
    if len(text) < 50:
        # Might be JSON response
        try:
            data = json.loads(body)
            text = json.dumps(data, indent=2)[:3000]
        except Exception:
            pass

    return {
        "content": f"Content from {url}:\n\n{text}",
        "data": {"url": url, "text_length": len(text)},
    }
