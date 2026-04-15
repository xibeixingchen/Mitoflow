"""Tests for circular coordinate support in boundary correction."""

import pytest
from mitoflow.annotate.boundary import (
    _correct_start_codon_conservative,
    _correct_stop_codon_conservative,
)
from mitoflow.models.genome import GenomeSequence
from mitoflow.models.gene import GeneAnnotation, ExonRecord, Strand
from mitoflow.db.manager import DBManager


def _make_test_gene_name(ann: GeneAnnotation) -> GeneAnnotation:
    """Rename to a gene not in EXPECTED_LENGTHS so correction actually runs."""
    return ann.model_copy(update={"gene_name": "test_gene_xyz"})


class TestCircularBoundaryCorrection:
    """Test start/stop codon search when gene crosses the origin."""

    def test_start_codon_search_crosses_origin_plus_strand(self):
        """Start codon correction should handle a gene whose search range wraps around origin."""
        # Genome: 30 bp circular
        # True gene: start=28 (ATG), 3 codons, stop=7-9 (TAA)
        # Positions 1-9:  GCT GCT TAA
        # Positions 10-27: N*18
        # Positions 28-30: ATG
        seq = "GCTGCTTAA" + "N" * 18 + "ATG"
        assert len(seq) == 30

        genome = GenomeSequence(seqid="test", sequence=seq, is_circular=True)

        # HMM start is exact (28), but search window (18..28) crosses origin
        ann = GeneAnnotation(
            gene_name="test_gene_xyz",
            gene_type="CDS",
            exons=[ExonRecord(start=28, end=9, strand=Strand.PLUS, number=1)],
            strand=Strand.PLUS,
        )

        db = DBManager()
        corrected = _correct_start_codon_conservative(ann, genome, db, search_range=10)

        # Should preserve the exact start codon at position 28
        assert corrected.exons[0].start == 28
        assert corrected.exons[0].end == 9

    def test_start_codon_search_crosses_origin_minus_strand(self):
        """Start codon correction on minus strand with origin-crossing search window."""
        # Forward sequence that when RC'd has ATG at transcription start
        # Transcription start on minus = highest coordinate (position 30)
        # Forward "CAT" at 28-30 -> RC = "ATG"
        # Then some coding sequence, then forward "ATT" at 1-3 -> RC = "TAA" (stop)
        seq = "ATT" + "AGC" * 8 + "CAT"  # 3 + 24 + 3 = 30 bp
        genome = GenomeSequence(seqid="test", sequence=seq, is_circular=True)

        # Gene on minus strand: transcription runs 30 -> 1
        # HMM says start=1, end=30 (exact boundaries)
        ann = GeneAnnotation(
            gene_name="test_gene_xyz",
            gene_type="CDS",
            exons=[ExonRecord(start=1, end=30, strand=Strand.MINUS, number=1)],
            strand=Strand.MINUS,
        )

        db = DBManager()
        corrected = _correct_start_codon_conservative(ann, genome, db, search_range=10)

        # Boundaries should stay exact
        assert corrected.exons[0].start == 1
        assert corrected.exons[0].end == 30

    def test_stop_codon_search_crosses_origin_plus_strand(self):
        """Stop codon search should find TAA when it sits just after the origin."""
        # Genome: 30 bp circular
        # Gene start=25, stop=3 (TAA) – stop codon crosses origin
        seq = "AAT" + "GCT" * 7 + "ATG" + "GCT"  # stop at 1-3? Need TAA
        # Let me build more carefully:
        # 1-3: TAA (stop)
        # 4-24: filler (GCT*7)
        # 25-27: ATG (start)
        # 28-30: GCT
        seq = "TAA" + "GCT" * 7 + "ATG" + "GCT"
        assert len(seq) == 30

        genome = GenomeSequence(seqid="test", sequence=seq, is_circular=True)

        ann = GeneAnnotation(
            gene_name="test_gene_xyz",
            gene_type="CDS",
            exons=[ExonRecord(start=25, end=30, strand=Strand.PLUS, number=1)],
            strand=Strand.PLUS,
        )

        db = DBManager()
        corrected = _correct_stop_codon_conservative(ann, genome, db, search_range=10)

        # Should extend to include the TAA at positions 1-3
        assert corrected.exons[0].end == 3
        assert corrected.exons[0].start == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
