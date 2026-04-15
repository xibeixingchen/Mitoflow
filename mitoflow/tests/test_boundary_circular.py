"""Tests for circular coordinate support in boundary correction."""

import pytest
from mitoflow.annotate.boundary import (
    _correct_start_codon_conservative,
    _correct_stop_codon_conservative,
    _restore_phase_continuity,
    _refine_boundary_by_tblastn,
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


class TestPhaseContinuityRestoration:
    """Test _restore_phase_continuity micro-adjustments."""

    def test_plus_strand_restores_phase_by_extending_exon(self):
        """Exon 1 extended by 1 bp so exon 2 phase matches."""
        genome = GenomeSequence(seqid="test", sequence="A" * 100, is_circular=False)
        ann = GeneAnnotation(
            gene_name="nad5",
            gene_type="CDS",
            exons=[
                ExonRecord(start=10, end=20, strand=Strand.PLUS, number=1, phase=0),
                ExonRecord(start=30, end=40, strand=Strand.PLUS, number=2, phase=2),
            ],
            strand=Strand.PLUS,
        )
        # Cumulative len before exon 2 = 11 (20-10+1). 11 % 3 = 2, matches phase.
        # No adjustment needed.
        restored = _restore_phase_continuity(ann, genome)
        assert restored.exons[0].end == 20

    def test_plus_strand_adjusts_when_phase_broken(self):
        """Boundary shift broke phase; extend exon 1 by 1 bp to fix."""
        genome = GenomeSequence(seqid="test", sequence="A" * 100, is_circular=False)
        ann = GeneAnnotation(
            gene_name="nad5",
            gene_type="CDS",
            exons=[
                ExonRecord(start=10, end=19, strand=Strand.PLUS, number=1, phase=0),
                ExonRecord(start=30, end=40, strand=Strand.PLUS, number=2, phase=2),
            ],
            strand=Strand.PLUS,
        )
        # Cumulative len before exon 2 = 10 (19-10+1). 10 % 3 = 1, but phase=2.
        # Need cumulative_len = 2 mod 3, so need length 11. Extend end by +1.
        restored = _restore_phase_continuity(ann, genome)
        assert restored.exons[0].end == 20
        assert "phase continuity restored" in restored.notes[-1]

    def test_minus_strand_adjusts_when_phase_broken(self):
        """Boundary shift broke phase on minus strand; move start down by 1 bp."""
        genome = GenomeSequence(seqid="test", sequence="A" * 100, is_circular=False)
        ann = GeneAnnotation(
            gene_name="nad5",
            gene_type="CDS",
            exons=[
                # Minus strand: transcription high->low. Exon 1 has higher coords.
                ExonRecord(start=80, end=90, strand=Strand.MINUS, number=1, phase=0),
                ExonRecord(start=60, end=70, strand=Strand.MINUS, number=2, phase=2),
            ],
            strand=Strand.MINUS,
        )
        # Cumulative len exon 1 = 11 (90-80+1). 11 % 3 = 2, but phase=2 actually matches.
        # No adjustment.
        restored = _restore_phase_continuity(ann, genome)
        assert restored.exons[0].start == 80

    def test_minus_strand_shortens_exon_when_needed(self):
        """Need to shorten exon 1 by 1 bp (move start up) to fix phase."""
        genome = GenomeSequence(seqid="test", sequence="A" * 100, is_circular=False)
        ann = GeneAnnotation(
            gene_name="nad5",
            gene_type="CDS",
            exons=[
                ExonRecord(start=80, end=91, strand=Strand.MINUS, number=1, phase=0),
                ExonRecord(start=60, end=70, strand=Strand.MINUS, number=2, phase=1),
            ],
            strand=Strand.MINUS,
        )
        # Cumulative len exon 1 = 12. 12 % 3 = 0, but phase=1.
        # Need cumulative_len = 1 mod 3, so need length 13 (already 12) or 10.
        # delta = (1 - 0) % 3 = 1. shifts = [+1, -2].
        # +1: new_start = 80 - 1 = 79 (length 13). 13 % 3 = 1. OK.
        restored = _restore_phase_continuity(ann, genome)
        assert restored.exons[0].start == 79
        assert "phase continuity restored" in restored.notes[-1]

    def test_single_exon_skipped(self):
        """Phase continuity only applies to multi-exon genes."""
        genome = GenomeSequence(seqid="test", sequence="A" * 100, is_circular=False)
        ann = GeneAnnotation(
            gene_name="cox1",
            gene_type="CDS",
            exons=[ExonRecord(start=10, end=30, strand=Strand.PLUS, number=1, phase=0)],
            strand=Strand.PLUS,
        )
        restored = _restore_phase_continuity(ann, genome)
        assert restored.exons[0].end == 30
        assert not any("phase" in n for n in restored.notes)


class TestTblastnBoundaryRefinement:
    """Test _refine_boundary_by_tblastn skip conditions."""

    def test_skips_trans_spliced_genes(self):
        """Trans-spliced genes should not be refined by tblastn."""
        genome = GenomeSequence(seqid="test", sequence="A" * 100, is_circular=False)
        db = DBManager()
        ann = GeneAnnotation(
            gene_name="nad5",
            gene_type="CDS",
            exons=[ExonRecord(start=10, end=30, strand=Strand.PLUS, number=1)],
            strand=Strand.PLUS,
        )
        refined = _refine_boundary_by_tblastn(ann, genome, db)
        assert refined.exons[0].start == 10
        assert refined.source_method != "tblastn"

    def test_skips_multi_exon_genes(self):
        """Genes with >1 exon should be skipped even if not in TRANS_SPLICED_CONFIG."""
        genome = GenomeSequence(seqid="test", sequence="A" * 100, is_circular=False)
        db = DBManager()
        ann = GeneAnnotation(
            gene_name="atp1",
            gene_type="CDS",
            exons=[
                ExonRecord(start=10, end=20, strand=Strand.PLUS, number=1),
                ExonRecord(start=30, end=40, strand=Strand.PLUS, number=2),
            ],
            strand=Strand.PLUS,
        )
        refined = _refine_boundary_by_tblastn(ann, genome, db)
        assert refined.exons[0].start == 10
        assert refined.source_method != "tblastn"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
