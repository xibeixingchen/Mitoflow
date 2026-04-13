"""Genome data models."""

from __future__ import annotations
from pydantic import BaseModel, computed_field


class ContigInfo(BaseModel):
    """Track original contig positions after merging."""
    original_id: str
    start: int  # 1-based in merged sequence
    end: int    # inclusive
    length: int


class GenomeSequence(BaseModel):
    """Represents an assembled mitochondrial genome."""
    seqid: str
    sequence: str
    is_circular: bool = True
    contig_map: list[ContigInfo] | None = None

    @computed_field
    @property
    def length(self) -> int:
        return len(self.sequence)

    @computed_field
    @property
    def gc_content(self) -> float:
        seq = self.sequence.upper()
        gc = seq.count("G") + seq.count("C")
        valid = sum(1 for b in seq if b in "ATGCN")
        return gc / valid * 100 if valid > 0 else 0.0

    @computed_field
    @property
    def reverse_complement(self) -> str:
        comp = str.maketrans("ATGCatgcNn", "TACGtacgNn")
        return self.sequence.translate(comp)[::-1]

    def subsequence(self, start: int, end: int) -> str:
        """Extract subsequence (1-based, inclusive)."""
        return self.sequence[start - 1 : end]

    def get_sequence_for_range(
        self, start: int, end: int, strand: int = 1
    ) -> str:
        """Get sequence for a range on given strand."""
        seq = self.subsequence(start, end)
        if strand == -1:
            comp = str.maketrans("ATGCatgcNn", "TACGtacgNn")
            return seq.translate(comp)[::-1]
        return seq
