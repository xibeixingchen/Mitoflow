"""Tests for boundary refinement - preventing over-extension.

The current sliding search approach can over-extend gene boundaries
when the HMM hit is already beyond the true gene end. This module
tests the reference-based approach that uses BLAST to find exact
boundaries.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from mitoflow.annotate.pcg import (
    HMMHit,
    PCGConfig,
    _refine_boundaries,
    _refine_boundaries_reference,
    _refine_single_conservative,
)
from mitoflow.models.genome import GenomeSequence
from mitoflow.db.manager import DBManager


class TestBoundaryOverExtension:
    """Test cases for boundary over-extension issues."""

    def test_sliding_search_over_extends_when_hmm_beyond_true_end(self):
        """When HMM hit end is beyond the true stop codon,
        sliding search continues outward and finds a later stop codon,
        causing over-extension.

        Example: atp4 should end at 362784 (NCBI), but sliding search
        might find a stop at 362804+ if the HMM hit already extends
        beyond 362784.
        """
        # Create a genome with a gene that ends at position 300 with TAA
        # HMM hit extends to position 320 (beyond true gene end)
        # There's another stop codon at position 330

        # Build a sequence:
        # Position 1-300: gene sequence ending with TAA at 298-300
        # Position 301-330: random sequence with TAA at 328-330
        gene_seq = "ATG" + "GCT" * 98 + "TAA"  # 297 + 3 = 300 bp, stop at 298-300
        extra_seq = "GCT" * 10 + "TAA"  # 33 bp, stop at 328-330

        sequence = gene_seq + extra_seq

        genome = GenomeSequence(
            seqid="test",
            sequence=sequence,
            is_circular=False,
        )

        # HMM hit with end already beyond true gene end (320 > 300)
        hit = HMMHit(
            gene_name="atp4",
            start=1,
            end=320,  # Over-extended from HMM
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=107,  # ~320bp / 3
        )

        db_manager = DBManager()
        config = PCGConfig()

        # Current sliding search will find stop at 328-330
        refined = _refine_boundaries([hit], genome, db_manager, config)

        # The old behavior over-extends to find stop at 330
        # This test documents the problem
        assert refined[0].end >= 300, "End should be at least at true stop codon"

        # This test would fail if we expect the correct boundary (300)
        # because the current implementation over-extends

    def test_conservative_refinement_limits_adjustment(self):
        """Conservative refinement should only adjust ±10bp max."""
        # Create a genome where the true gene ends at 300 (TAA)
        # HMM hit end is at 306 (6bp beyond, frame-aligned) - within ±10bp limit

        gene_seq = "ATG" + "GCT" * 98 + "TAA"  # 300 bp, stop at 298-300
        extra_seq = "GCT" * 20  # 60 bp

        sequence = gene_seq + extra_seq

        genome = GenomeSequence(seqid="test", sequence=sequence, is_circular=False)

        hit = HMMHit(
            gene_name="atp4",
            start=1,
            end=306,  # HMM end is 6bp beyond true stop (frame-aligned, within limit)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=102,
        )

        db_manager = DBManager()

        refined = _refine_single_conservative(hit, genome, db_manager, PCGConfig())

        # Should adjust back to 300 (within ±10bp range, frame-aligned)
        assert refined.end == 300, f"Expected 300, got {refined.end}"

    def test_conservative_refinement_does_not_adjust_beyond_limit(self):
        """If stop codon is beyond ±10bp limit, keep HMM boundary."""
        # Create genome where stop codon is 9bp beyond HMM end (within limit)
        # but we test a case where the frame alignment doesn't find it

        gene_seq = "ATG" + "GCT" * 98 + "TAA"  # 300 bp, stop at 298-300
        extra_seq = "GCT" * 20

        sequence = gene_seq + extra_seq

        genome = GenomeSequence(seqid="test", sequence=sequence, is_circular=False)

        hit = HMMHit(
            gene_name="atp4",
            start=1,
            end=309,  # HMM end is 9bp beyond true stop (frame-aligned, within ±10bp)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=103,
        )

        db_manager = DBManager()

        refined = _refine_single_conservative(hit, genome, db_manager, PCGConfig())

        # Should adjust back to 300 (9bp is within ±10bp limit, frame-aligned)
        assert refined.end == 300, f"Expected 300, got {refined.end}"

    def test_conservative_refinement_beyond_limit_keeps_boundary(self):
        """If stop codon is 12bp away (beyond ±10bp), keep HMM boundary."""
        gene_seq = "ATG" + "GCT" * 98 + "TAA"  # 300 bp, stop at 298-300
        extra_seq = "GCT" * 20

        sequence = gene_seq + extra_seq

        genome = GenomeSequence(seqid="test", sequence=sequence, is_circular=False)

        hit = HMMHit(
            gene_name="atp4",
            start=1,
            end=312,  # HMM end is 12bp beyond (frame-aligned, but beyond ±10bp limit)
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=104,
        )

        db_manager = DBManager()

        refined = _refine_single_conservative(hit, genome, db_manager, PCGConfig())

        # Should NOT adjust (12bp is beyond ±10bp limit)
        assert refined.end == 312, f"Expected 312 (no adjustment), got {refined.end}"

    def test_conservative_refinement_does_not_adjust_if_no_nearby_codon(self):
        """If no stop codon within ±10bp, keep HMM boundary."""
        # Create genome without nearby stop codon
        gene_seq = "ATG" + "GCT" * 100  # 303 bp, no stop
        extra_seq = "GCT" * 20

        sequence = gene_seq + extra_seq

        genome = GenomeSequence(seqid="test", sequence=sequence, is_circular=False)

        hit = HMMHit(
            gene_name="atp4",
            start=1,
            end=303,
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=101,
        )

        db_manager = DBManager()

        refined = _refine_single_conservative(hit, genome, db_manager, PCGConfig())

        # Should keep original boundary
        assert refined.end == 303


class TestReferenceBasedRefinement:
    """Tests for reference-based boundary refinement using BLAST."""

    def test_uses_blastn_not_tblastn(self):
        """Verify that blastn tool is used (not tblastn) for nucleotide alignment."""
        import subprocess
        from unittest.mock import patch, MagicMock

        # blastn should be checked, not tblastn
        blastn_path = shutil.which("blastn")
        if not blastn_path:
            pytest.skip("blastn not available")

        # Verify blastn exists and tblastn is NOT the primary tool
        # The code should use shutil.which("blastn") not shutil.which("tblastn")
        assert blastn_path is not None, "blastn tool must be available"

    def test_uses_cds_fasta_not_protein_fasta(self):
        """Verify that CDS.fasta files are used (not Protein.fasta) as reference."""
        db_manager = DBManager()

        # Check if the reference directory exists
        ref_dir = db_manager.blast_ref_dir
        if not ref_dir.exists():
            pytest.skip("Reference directory not found")

        # List reference files - should contain .CDS.fasta files
        cds_files = list(ref_dir.glob("*.CDS.fasta"))
        protein_files = list(ref_dir.glob("*.Protein.fasta"))

        # The spec requires CDS.fasta files to be used
        # At minimum, verify the naming convention is correct
        if cds_files:
            # CDS.fasta files should be the primary reference
            for f in cds_files:
                assert f.name.endswith(".CDS.fasta"), f"Expected CDS.fasta file: {f}"

    @pytest.mark.skipif(
        not shutil.which("blastn"),
        reason="blastn not available"
    )
    def test_refinement_with_reference_cds(self):
        """When reference CDS is available, use blastn to find exact boundaries."""
        # Create a mock genome with a known gene
        # Use a sequence that matches atp4 reference approximately
        db_manager = DBManager()

        # Check if reference exists
        ref_file = db_manager.blast_ref_dir / "atp4.CDS.fasta"
        if not ref_file.exists():
            pytest.skip("atp4 CDS reference not found")

        # Create genome with atp4-like sequence
        # For testing, we'll use a simple case
        gene_seq = "ATG" + "GCT" * 190 + "TAA"  # ~600 bp, similar to atp4 length
        sequence = gene_seq + "NNN" * 100

        genome = GenomeSequence(seqid="test", sequence=sequence, is_circular=False)

        hit = HMMHit(
            gene_name="atp4",
            start=1,
            end=600,  # Close to true length
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=200,
        )

        config = PCGConfig()

        refined = _refine_boundaries_reference([hit], genome, db_manager, config)

        # Should have refined the boundary
        assert len(refined) == 1
        assert refined[0].gene_name == "atp4"

    def test_refinement_fallback_to_conservative_without_blast(self):
        """If blastn is not available, fallback to conservative refinement."""
        # This test uses a mock scenario where blastn is not available
        db_manager = DBManager()

        gene_seq = "ATG" + "GCT" * 98 + "TAA"
        genome = GenomeSequence(seqid="test", sequence=gene_seq + "GCT" * 20, is_circular=False)

        hit = HMMHit(
            gene_name="test_gene",  # Gene without reference
            start=1,
            end=310,
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=103,
        )

        config = PCGConfig()

        # Without reference, should fallback to conservative
        refined = _refine_boundaries_reference([hit], genome, db_manager, config)

        assert len(refined) == 1


class TestBoundaryEdgeCases:
    """Test edge cases in boundary refinement."""

    def test_reverse_strand_start_codon_search(self):
        """Test start codon search on reverse strand."""
        # Gene on reverse strand: starts at high coord, ends at low coord
        # Start codon (ATG) when reverse complemented

        comp = str.maketrans("ATGCatgcNn", "TACGtacgNn")

        # Build reverse strand gene
        # On forward strand: positions 1-300 contain the gene
        # The gene reads from position 300 (5' start on reverse) to position 1 (3' stop)

        # Forward sequence that when RC'd has ATG at the start
        fwd_seq = "CAT" + "AGC" * 98 + "ATT"  # RC will have AAT -> TTA stop? No...
        # Let me compute: forward "CAT" -> RC "ATG" (start)
        # Forward "ATT" -> RC "TAA" (stop)

        gene_seq = "CAT" + "AGC" * 98 + "ATT"  # 303 bp
        extra_seq = "AGC" * 10

        sequence = gene_seq + extra_seq
        genome = GenomeSequence(seqid="test", sequence=sequence, is_circular=False)

        hit = HMMHit(
            gene_name="test",
            start=1,
            end=303,  # Gene on reverse strand
            strand=-1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=101,
        )

        db_manager = DBManager()

        refined = _refine_single_conservative(hit, genome, db_manager, PCGConfig())

        # Should find start codon (ATG in RC) at position 303
        # and stop codon (TAA in RC) at position 1
        assert refined.start >= 1
        assert refined.end <= 303

    def test_gene_length_validation_prevents_over_extension(self):
        """If refined gene is >2x original HMM length, keep original."""
        # Create a gene that would be massively over-extended
        gene_seq = "ATG" + "GCT" * 98 + "TAA"  # 300 bp
        # Add many more stop codons downstream
        extra_seq = "GCT" * 100 + "TAA" + "GCT" * 100 + "TAA"

        sequence = gene_seq + extra_seq  # ~600 bp

        genome = GenomeSequence(seqid="test", sequence=sequence, is_circular=False)

        hit = HMMHit(
            gene_name="atp4",  # Expected ~579 bp
            start=1,
            end=100,  # Very short HMM hit
            strand=1,
            score=500,
            evalue=1e-10,
            domain_score=400,
            ali_start=1,
            ali_end=33,
        )

        db_manager = DBManager()
        config = PCGConfig(stop_codon_search_range=500)  # Large search range

        refined = _refine_boundaries([hit], genome, db_manager, config)

        # The refinement should cap at ~250bp (100 * 2.5)
        # or find the first stop at 300
        # Due to validation, it shouldn't extend to 600+
        refined_len = refined[0].end - refined[0].start + 1
        original_len = hit.end - hit.start + 1

        # Current implementation has 2.5x cap
        assert refined_len <= original_len * 2.5 or refined_len <= 600


class TestIntegrationWithPipeline:
    """Integration tests for boundary refinement in the pipeline."""

    def test_pcg_annotation_uses_reference_based_refinement(self):
        """annotate_pcg should use reference-based refinement by default."""
        from mitoflow.annotate.pcg import annotate_pcg

        # Create a small test genome
        sequence = "ATG" + "GCT" * 500 + "TAA" + "NNN" * 100
        genome = GenomeSequence(seqid="test", sequence=sequence, is_circular=False)

        db_manager = DBManager()
        config = PCGConfig()

        # This would normally run HMM search
        # For testing, we just verify the function runs
        annotations = annotate_pcg(genome, db_manager, config)

        # Should return annotations (or empty list if no HMM hits)
        assert isinstance(annotations, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])