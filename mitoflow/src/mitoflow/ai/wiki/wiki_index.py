"""Wiki index for fast knowledge retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

_WIKI_DIR = Path(__file__).parent / "pages"


class WikiIndex:
    """Index and retrieve wiki pages by topic, keyword, and entity."""

    def __init__(self, wiki_dir: Optional[Path] = None) -> None:
        self._wiki_dir = wiki_dir or _WIKI_DIR
        self._pages: Optional[List[Dict[str, Any]]] = None

    @property
    def pages(self) -> List[Dict[str, Any]]:
        if self._pages is None:
            self._pages = self._load_pages()
        return self._pages

    def _load_pages(self) -> List[Dict[str, Any]]:
        """Load all wiki pages from disk."""
        pages = []
        if not self._wiki_dir.exists():
            return pages
        for md_file in sorted(self._wiki_dir.glob("*.md")):
            page = self._parse_page(md_file)
            if page:
                pages.append(page)
        return pages

    def _parse_page(self, path: Path) -> Optional[Dict[str, Any]]:
        """Parse a markdown wiki page."""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return None

        lines = content.strip().split("\n")
        title = path.stem.replace("_", " ").title()
        tags: List[str] = []
        entities: List[str] = []
        references: List[str] = []
        body_lines: List[str] = []

        in_frontmatter = False
        for line in lines:
            if line.strip() == "---" and not in_frontmatter:
                in_frontmatter = True
                continue
            if line.strip() == "---" and in_frontmatter:
                in_frontmatter = False
                continue
            if in_frontmatter:
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip()
                elif line.startswith("tags:"):
                    tags = [t.strip() for t in line.split(":", 1)[1].split(",")]
                elif line.startswith("entities:"):
                    entities = [e.strip() for e in line.split(":", 1)[1].split(",")]
                elif line.startswith("references:"):
                    references = [r.strip() for r in line.split(":", 1)[1].split(",")]
            else:
                body_lines.append(line)

        # Extract headings for structure
        headings = [l.strip("# ").strip() for l in body_lines if l.startswith("#")]

        return {
            "file": path.name,
            "title": title,
            "tags": tags,
            "entities": entities,
            "references": references,
            "headings": headings,
            "content": "\n".join(body_lines),
            "summary": self._extract_summary(body_lines),
        }

    def _extract_summary(self, lines: List[str]) -> str:
        """Extract first paragraph as summary."""
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("|"):
                return stripped[:200]
        return ""

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search wiki pages by keyword."""
        query_lower = query.lower()
        results = []
        for page in self.pages:
            score = 0
            if query_lower in page["title"].lower():
                score += 10
            if any(query_lower in e.lower() for e in page["entities"]):
                score += 8
            if any(query_lower in t.lower() for t in page["tags"]):
                score += 5
            if query_lower in page["summary"].lower():
                score += 3
            if query_lower in page["content"].lower():
                score += 1
            if score > 0:
                results.append({**page, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_page(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific wiki page by filename."""
        name_lower = name.lower().replace(" ", "_")
        for page in self.pages:
            if page["file"].lower().replace(".md", "") == name_lower:
                return page
        return None

    def list_pages(self) -> List[Dict[str, str]]:
        """List all wiki pages with titles."""
        return [{"file": p["file"], "title": p["title"], "tags": p["tags"]} for p in self.pages]

    def get_entity_pages(self, entity: str) -> List[Dict[str, Any]]:
        """Get all pages mentioning an entity."""
        entity_lower = entity.lower()
        results = []
        for page in self.pages:
            if (entity_lower in [e.lower() for e in page["entities"]] or
                entity_lower in page["content"].lower()):
                results.append(page)
        return results
