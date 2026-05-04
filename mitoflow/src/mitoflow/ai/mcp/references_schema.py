"""Data models for the literature reference database."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReferenceType(str, Enum):
    """Type of reference."""

    TOOL = "tool"           # Software/tool paper
    METHOD = "method"       # Methodology paper
    DATABASE = "database"   # Database/resource
    REVIEW = "review"       # Review article
    APPLICATION = "application"  # Application study
    GENOME = "genome"       # Genome assembly/annotation


class EntityType(str, Enum):
    """Type of entity referenced."""

    GENE = "gene"
    SPECIES = "species"
    TOOL = "tool"
    METHOD = "method"
    PATHWAY = "pathway"
    COMPLEX = "complex"
    CONCEPT = "concept"


class Reference(BaseModel):
    """A literature reference with metadata."""

    id: str = Field(description="Unique reference ID (e.g. 'ref_001')")
    doi: Optional[str] = None
    pmid: Optional[str] = None
    title: str
    authors: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    year: Optional[int] = None
    abstract: Optional[str] = None
    ref_type: ReferenceType = ReferenceType.APPLICATION
    tags: List[str] = Field(default_factory=list)
    entities: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of {type, name} pairs for linked entities",
    )
    key_findings: List[str] = Field(default_factory=list)
    url: Optional[str] = None


class EntityReference(BaseModel):
    """An entity linked to its references."""

    entity_type: EntityType
    entity_name: str
    description: str = ""
    references: List[str] = Field(default_factory=list, description="Reference IDs")
    properties: Dict[str, Any] = Field(default_factory=dict)


class ReferenceDatabase(BaseModel):
    """The complete reference database."""

    version: str = "1.0.0"
    references: List[Reference] = Field(default_factory=list)
    entities: List[EntityReference] = Field(default_factory=list)

    def get_reference(self, ref_id: str) -> Optional[Reference]:
        for ref in self.references:
            if ref.id == ref_id:
                return ref
        return None

    def get_entity(self, entity_type: str, entity_name: str) -> Optional[EntityReference]:
        name_lower = entity_name.lower()
        for ent in self.entities:
            if ent.entity_type == entity_type and ent.entity_name.lower() == name_lower:
                return ent
        return None

    def search_references(self, query: str) -> List[Reference]:
        query_lower = query.lower()
        results = []
        for ref in self.references:
            if (query_lower in ref.title.lower() or
                query_lower in (ref.abstract or "").lower() or
                any(query_lower in tag.lower() for tag in ref.tags) or
                any(query_lower in f.lower() for f in ref.key_findings)):
                results.append(ref)
        return results

    def get_entity_references(self, entity_type: str, entity_name: str) -> List[Reference]:
        """Get all references for an entity."""
        ent = self.get_entity(entity_type, entity_name)
        if not ent:
            return []
        return [ref for ref in self.references if ref.id in ent.references]
