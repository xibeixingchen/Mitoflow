"""Knowledge base manager for the MCP reference system."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .references_schema import EntityReference, Reference, ReferenceDatabase, ReferenceType

_DATA_DIR = Path(__file__).parent


class KnowledgeBase:
    """Manages the literature reference database and provides cited lookups."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or (_DATA_DIR / "references.json")
        self._db: Optional[ReferenceDatabase] = None

    @property
    def db(self) -> ReferenceDatabase:
        if self._db is None:
            with open(self._db_path, encoding="utf-8") as f:
                data = json.load(f)
            self._db = ReferenceDatabase(**data)
        return self._db

    def reload(self) -> None:
        """Reload the database from disk."""
        self._db = None

    def format_citation(self, ref: Reference) -> str:
        """Format a reference as a short citation string."""
        parts = []
        if ref.authors:
            if len(ref.authors) > 2:
                parts.append(f"{ref.authors[0]} et al.")
            else:
                parts.append(", ".join(ref.authors))
        if ref.year:
            parts.append(f"({ref.year})")
        if ref.journal:
            parts.append(ref.journal)
        if ref.doi:
            parts.append(f"DOI: {ref.doi}")
        elif ref.pmid:
            parts.append(f"PMID: {ref.pmid}")
        return " — ".join(parts)

    def lookup_gene(self, gene_name: str) -> Dict[str, Any]:
        """Look up a gene with full citations."""
        # Get entity info
        entity = self.db.get_entity("gene", gene_name)
        # Also check concept entities
        if not entity:
            entity = self.db.get_entity("concept", gene_name)

        if not entity:
            # Try searching
            refs = self.db.search_references(gene_name)
            if refs:
                return {
                    "entity": gene_name,
                    "description": f"References mentioning '{gene_name}'",
                    "references": [self._ref_to_dict(r) for r in refs[:5]],
                }
            return {"entity": gene_name, "found": False, "message": f"No information found for '{gene_name}'"}

        refs = [self.db.get_reference(rid) for rid in entity.references]
        refs = [r for r in refs if r is not None]

        return {
            "entity": entity.entity_name,
            "type": entity.entity_type,
            "description": entity.description,
            "properties": entity.properties,
            "references": [self._ref_to_dict(r) for r in refs],
        }

    def lookup_tool(self, tool_name: str) -> Dict[str, Any]:
        """Look up a tool with full citations."""
        entity = self.db.get_entity("tool", tool_name)
        if not entity:
            refs = self.db.search_references(tool_name)
            if refs:
                return {
                    "tool": tool_name,
                    "references": [self._ref_to_dict(r) for r in refs[:5]],
                }
            return {"tool": tool_name, "found": False}

        refs = [self.db.get_reference(rid) for rid in entity.references]
        refs = [r for r in refs if r is not None]

        return {
            "tool": entity.entity_name,
            "description": entity.description,
            "properties": entity.properties,
            "references": [self._ref_to_dict(r) for r in refs],
        }

    def search_literature(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search literature by keyword."""
        refs = self.db.search_references(query)
        return [self._ref_to_dict(r) for r in refs[:limit]]

    def get_assembly_tools(self) -> List[Dict[str, Any]]:
        """List all assembly tools with citations."""
        results = []
        for ref in self.db.references:
            if "assembly" in ref.tags:
                results.append(self._ref_to_dict(ref))
        return results

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """List all tools with citations."""
        results = []
        for ent in self.db.entities:
            if ent.entity_type == "tool":
                refs = [self.db.get_reference(rid) for rid in ent.references]
                refs = [r for r in refs if r is not None]
                results.append({
                    "tool": ent.entity_name,
                    "description": ent.description,
                    "properties": ent.properties,
                    "references": [self.format_citation(r) for r in refs],
                })
        return results

    def get_concept_info(self, concept: str) -> Dict[str, Any]:
        """Get information about a concept with citations."""
        return self.lookup_gene(concept)  # Same lookup logic

    def format_response_with_citations(self, entity_type: str, entity_name: str) -> str:
        """Format a response string with inline citations."""
        if entity_type == "tool":
            info = self.lookup_tool(entity_name)
        else:
            info = self.lookup_gene(entity_name)

        if not info.get("found", True):
            return f"No information found for {entity_name}."

        lines = []
        desc = info.get("description", "")
        if desc:
            lines.append(desc)

        props = info.get("properties", {})
        if props:
            for k, v in props.items():
                lines.append(f"  {k}: {v}")

        refs = info.get("references", [])
        if refs:
            lines.append("\nReferences:")
            for ref in refs:
                citation = ref.get("citation", "")
                if citation:
                    lines.append(f"  [{ref.get('id', '')}] {citation}")
                if ref.get("key_findings"):
                    for finding in ref["key_findings"][:2]:
                        lines.append(f"    • {finding}")

        return "\n".join(lines)

    def _ref_to_dict(self, ref: Reference) -> Dict[str, Any]:
        return {
            "id": ref.id,
            "title": ref.title,
            "authors": ref.authors,
            "journal": ref.journal,
            "year": ref.year,
            "doi": ref.doi,
            "pmid": ref.pmid,
            "citation": self.format_citation(ref),
            "key_findings": ref.key_findings,
            "tags": ref.tags,
        }
