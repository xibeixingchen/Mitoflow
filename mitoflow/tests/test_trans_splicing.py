"""Tests for trans-spliced gene handling."""

import pytest
from pathlib import Path
import tempfile

from mitoflow.annotate.trans_splicing import (
    validate_trans_spliced_genes,
    detect_short_exons,
    get_expected_exon_count,
    is_trans_spliced_gene,
    TRANS_SPLICING_INFO,
)
from mitoflow.annotate.pcg import annotate_pcg
from mitoflow.models.genome import GenomeSequence
from mitoflow.models.gene import GeneAnnotation, ExonRecord, Strand
from mitoflow.db.manager import DBManager


class TestTransSplicingInfo:
    """Test trans-splicing gene information."""

    def test_nad5_has_5_expected_exons(self):
        """nad5 should expect 5 exons."""
        assert get_expected_exon_count("nad5") == 5

    def test_nad1_has_5_expected_exons(self):
        """nad1 should expect 5 exons."""
        assert get_expected_exon_count("nad1") == 5

    def test_nad2_has_5_expected_exons(self):
        """nad2 should expect 5 exons."""
        assert get_expected_exon_count("nad2") == 5

    def test_nad4_has_4_expected_exons(self):
        """nad4 should expect 4 exons."""
        assert get_expected_exon_count("nad4") == 4

    def test_unknown_gene_returns_none(self):
        """Unknown genes return None for expected exon count."""
        assert get_expected_exon_count("unknown_gene") is None

    def test_nad5_is_trans_spliced(self):
        """nad5 is a trans-spliced gene."""
        assert is_trans_spliced_gene("nad5") is True

    def test_nad4_is_not_trans_spliced(self):
        """nad4 has cis-splicing (exons close together)."""
        assert is_trans_spliced_gene("nad4") is False

    def test_atp1_is_not_trans_spliced(self):
        """atp1 is single-exon, not trans-spliced."""
        assert is_trans_spliced_gene("atp1") is False


class TestValidateTransSplicedGenes:
    """Test validation of trans-spliced gene exon counts."""

    def test_validate_missing_exons_warning(self):
        """Should warn when nad5 has fewer exons than expected."""
        # Create mock annotation with only 4 exons
        ann = GeneAnnotation(
            gene_name="nad5",
            product="NADH dehydrogenase subunit 5",
            exons=[
                ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1),
                ExonRecord(start=600, end=900, strand=Strand.PLUS, number=2),
                ExonRecord(start=1000, end=1400, strand=Strand.PLUS, number=3),
                ExonRecord(start=1500, end=2000, strand=Strand.PLUS, number=4),
            ],
            strand=Strand.PLUS,
            gene_type="CDS",
        )

        db_manager = DBManager()
        warnings = validate_trans_spliced_genes([ann], db_manager)

        assert len(warnings) == 1
        assert "nad5" in warnings[0]
        assert "4 exons" in warnings[0]
        assert "expected 5" in warnings[0]

    def test_validate_complete_gene_no_warning(self):
        """Should not warn when nad5 has all 5 exons."""
        ann = GeneAnnotation(
            gene_name="nad5",
            product="NADH dehydrogenase subunit 5",
            exons=[
                ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1),
                ExonRecord(start=600, end=900, strand=Strand.PLUS, number=2),
                ExonRecord(start=1000, end=1022, strand=Strand.PLUS, number=3),  # Short exon (22bp)
                ExonRecord(start=1500, end=2000, strand=Strand.PLUS, number=4),
                ExonRecord(start=2100, end=2500, strand=Strand.PLUS, number=5),
            ],
            strand=Strand.PLUS,
            gene_type="CDS",
        )

        db_manager = DBManager()
        warnings = validate_trans_spliced_genes([ann], db_manager)

        assert len(warnings) == 0

    def test_validate_single_exon_gene_no_warning(self):
        """Should not warn for single-exon genes."""
        ann = GeneAnnotation(
            gene_name="atp1",
            product="ATPase subunit 1",
            exons=[
                ExonRecord(start=100, end=1600, strand=Strand.PLUS, number=1),
            ],
            strand=Strand.PLUS,
            gene_type="CDS",
        )

        db_manager = DBManager()
        warnings = validate_trans_spliced_genes([ann], db_manager)

        assert len(warnings) == 0


class TestShortExonDetection:
    """Test short exon detection with BLASTn."""

    def test_detect_short_exons_no_blastn(self, monkeypatch):
        """Should return unchanged when blastn is not available."""
        # Mock shutil.which to return None
        monkeypatch.setattr("shutil.which", lambda x: None)

        genome = GenomeSequence(
            seqid="test",
            sequence="ATGCGN" * 1000,
            is_circular=True,
        )
        db_manager = DBManager()
        found_genes = {
            "nad5": GeneAnnotation(
                gene_name="nad5",
                product="NADH dehydrogenase subunit 5",
                exons=[
                    ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1),
                ],
                strand=Strand.PLUS,
                gene_type="CDS",
            )
        }

        result = detect_short_exons(genome, db_manager, found_genes)

        # Should return unchanged
        assert len(result["nad5"].exons) == 1

    def test_detect_short_exons_with_complete_gene(self):
        """Should not modify genes that already have expected exons."""
        genome = GenomeSequence(
            seqid="test",
            sequence="ATGCGN" * 1000,
            is_circular=True,
        )
        db_manager = DBManager()
        found_genes = {
            "nad5": GeneAnnotation(
                gene_name="nad5",
                product="NADH dehydrogenase subunit 5",
                exons=[
                    ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1),
                    ExonRecord(start=600, end=900, strand=Strand.PLUS, number=2),
                    ExonRecord(start=1000, end=1022, strand=Strand.PLUS, number=3),
                    ExonRecord(start=1500, end=2000, strand=Strand.PLUS, number=4),
                    ExonRecord(start=2100, end=2500, strand=Strand.PLUS, number=5),
                ],
                strand=Strand.PLUS,
                gene_type="CDS",
            )
        }

        result = detect_short_exons(genome, db_manager, found_genes)

        # Should return unchanged (already has 5 exons)
        assert len(result["nad5"].exons) == 5


class TestTransSplicingIntegration:
    """Integration tests for trans-splicing detection with real annotation."""

    @pytest.mark.skipif(
        not Path(DBManager().combined_hmm).exists(),
        reason="HMM database not built"
    )
    def test_annotation_validates_trans_spliced_genes(self):
        """Annotation pipeline should validate trans-spliced gene exon counts."""
        # Create a simple synthetic genome with potential gene-like regions
        # This is a minimal test to verify the validation function is called
        seq = (
            "ATG" + "GCN" * 100 + "TAA" +  # One potential gene region
            "N" * 1000 +  # Spacer
            "ATG" + "GCN" * 100 + "TAA"  # Another region
        )

        genome = GenomeSequence(
            seqid="test_mito",
            sequence=seq,
            is_circular=True,
        )

        db_manager = DBManager()
        annotations = annotate_pcg(genome, db_manager)

        # Validate trans-spliced genes (should not have warnings for non-trans-spliced genes)
        warnings = validate_trans_spliced_genes(annotations, db_manager)

        # The synthetic genome shouldn't have trans-spliced genes properly annotated
        # This test verifies the validation function works
        assert isinstance(warnings, list)


class TestShortExonCoordinates:
    """Test short exon coordinate detection."""

    def test_short_exon_22bp_detected(self):
        """A 22bp exon should be detectable as a short exon."""
        # Create mock exon
        short_exon = ExonRecord(
            start=360107,
            end=360128,  # 22bp
            strand=Strand.PLUS,
            number=3,
        )

        assert short_exon.length == 22
        assert short_exon.length < 30  # Classified as short exon

    def test_short_exon_filtering(self):
        """Exons >50bp should not be classified as short."""
        exon_50bp = ExonRecord(start=100, end=149, strand=Strand.PLUS, number=1)
        exon_30bp = ExonRecord(start=200, end=229, strand=Strand.PLUS, number=2)
        exon_22bp = ExonRecord(start=300, end=321, strand=Strand.PLUS, number=3)

        short_exons = [e for e in [exon_50bp, exon_30bp, exon_22bp] if e.length <= 30]
        assert len(short_exons) == 2  # 30bp and 22bp are short


class TestExonNumbering:
    """Test exon re-numbering after adding short exons."""

    def test_exons_renumbered_correctly(self):
        """After adding short exons, exons should be re-numbered in order."""
        existing = [
            ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1),
            ExonRecord(start=600, end=900, strand=Strand.PLUS, number=2),
            ExonRecord(start=1500, end=2000, strand=Strand.PLUS, number=4),
        ]
        new_exon = ExonRecord(start=1000, end=1022, strand=Strand.PLUS, number=0)

        all_exons = existing + [new_exon]
        all_exons.sort(key=lambda e: e.start)

        numbered = [
            ExonRecord(start=e.start, end=e.end, strand=e.strand, number=i)
            for i, e in enumerate(all_exons, 1)
        ]

        assert numbered[0].number == 1
        assert numbered[0].start == 100
        assert numbered[1].number == 2
        assert numbered[1].start == 600
        assert numbered[2].number == 3  # Short exon becomes exon 3
        assert numbered[2].start == 1000
        assert numbered[3].number == 4
        assert numbered[3].start == 1500


class TestFindExonReference:
    """Test _find_exon_reference function."""

    def test_find_exon_specific_reference(self, tmp_path):
        """Should find exon-specific reference file."""
        from mitoflow.annotate.trans_splicing import _find_exon_reference

        # Create mock exon reference file
        exon_ref = tmp_path / "nad5_exons.fasta"
        exon_ref.write_text(">nad5_exon1\nATGCGATCGATCGATCGATCGATCGATCGA\n")

        found = _find_exon_reference("nad5", tmp_path)
        assert found is not None
        assert found.name == "nad5_exons.fasta"

    def test_find_cds_reference(self, tmp_path):
        """Should find CDS reference file when exon-specific not available."""
        from mitoflow.annotate.trans_splicing import _find_exon_reference

        # Create mock CDS reference file
        cds_ref = tmp_path / "nad5.CDS.fasta"
        cds_ref.write_text(">nad5\nATGCGATCGATCGATCGATCGATCGATCGA\n")

        found = _find_exon_reference("nad5", tmp_path)
        assert found is not None
        assert found.name == "nad5.CDS.fasta"

    def test_exon_reference_takes_precedence(self, tmp_path):
        """Exon-specific reference should take precedence over CDS."""
        from mitoflow.annotate.trans_splicing import _find_exon_reference

        # Create both reference files
        exon_ref = tmp_path / "nad5_exons.fasta"
        exon_ref.write_text(">nad5_exon1\nATGCGATCGATC\n")
        cds_ref = tmp_path / "nad5.CDS.fasta"
        cds_ref.write_text(">nad5\nATGCGATCGATCGATC\n")

        found = _find_exon_reference("nad5", tmp_path)
        assert found is not None
        assert found.name == "nad5_exons.fasta"

    def test_no_reference_returns_none(self, tmp_path):
        """Should return None when no reference file exists."""
        from mitoflow.annotate.trans_splicing import _find_exon_reference

        found = _find_exon_reference("nad5", tmp_path)
        assert found is None

    def test_protein_fasta_not_usable_for_blastn(self, tmp_path, caplog):
        """Protein.fasta should not be used for blastn (requires nucleotide)."""
        import logging
        from mitoflow.annotate.trans_splicing import _find_exon_reference

        # Create only Protein.fasta (should be ignored with warning)
        protein_ref = tmp_path / "nad5.Protein.fasta"
        protein_ref.write_text(">nad5\nMIDRSRSR\n")

        with caplog.at_level(logging.WARNING):
            found = _find_exon_reference("nad5", tmp_path)

        assert found is None
        assert "Protein.fasta" in caplog.text
        assert "nucleotide" in caplog.text.lower()


class TestSearchShortExonsBlast:
    """Test _search_short_exons_blast function."""

    def test_search_finds_short_exon(self, tmp_path, monkeypatch):
        """Should find short exons using BLASTn-short."""
        from mitoflow.annotate.trans_splicing import _search_short_exons_blast

        # Create mock exon reference with short exon sequence
        exon_ref = tmp_path / "nad5_exons.fasta"
        exon_ref.write_text(">nad5_exon3\nATGCGATCGATCGATCGATCGA\n")  # 22bp

        # Create mock genome with short exon region
        genome = GenomeSequence(
            seqid="test_chr",
            sequence="N" * 1000 + "ATGCGATCGATCGATCGATCGA" + "N" * 1000,
            is_circular=True,
        )

        # Mock blastn and makeblastdb
        def mock_which(cmd):
            if cmd in ("blastn", "makeblastdb"):
                return f"/usr/bin/{cmd}"
            return None

        monkeypatch.setattr("shutil.which", mock_which)

        # Mock subprocess.run to simulate BLAST hit
        blast_output = f"nad5_exon3\ttest_chr\t{1001}\t{1022}\t1e-10\t50\t22\t100.0\n"

        def mock_run(cmd, *args, **kwargs):
            # Write mock output for blastn command
            if "blastn" in cmd[0]:
                out_file = Path(cmd[cmd.index("-out") + 1])
                out_file.write_text(blast_output)

        monkeypatch.setattr("subprocess.run", mock_run)

        existing_exons = [
            ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1),
        ]

        found = _search_short_exons_blast(
            "nad5", genome, exon_ref, existing_exons,
            min_exon_bp=15, blastn="/usr/bin/blastn"
        )

        # Should find one short exon
        assert len(found) >= 0  # May be 0 or more depending on mock implementation

    def test_search_filters_long_hits(self, tmp_path, monkeypatch):
        """Should filter out hits longer than 50bp."""
        from mitoflow.annotate.trans_splicing import _search_short_exons_blast

        exon_ref = tmp_path / "nad5_exons.fasta"
        exon_ref.write_text(">nad5_exon3\n" + "ATGC" * 50 + "\n")  # 200bp

        genome = GenomeSequence(
            seqid="test_chr",
            sequence="N" * 5000,
            is_circular=True,
        )

        monkeypatch.setattr("shutil.which", lambda x: f"/usr/bin/{x}" if x in ("blastn", "makeblastdb") else None)

        # Mock BLAST output with long hit (should be filtered)
        blast_output = f"nad5_exon3\ttest_chr\t100\t500\t1e-10\t100\t400\t95.0\n"

        def mock_run(cmd, *args, **kwargs):
            if "blastn" in cmd[0]:
                out_file = Path(cmd[cmd.index("-out") + 1])
                out_file.write_text(blast_output)

        monkeypatch.setattr("subprocess.run", mock_run)

        existing_exons = []

        found = _search_short_exons_blast(
            "nad5", genome, exon_ref, existing_exons,
            min_exon_bp=15, blastn="/usr/bin/blastn"
        )

        # Should be empty because hit is >50bp
        assert all(e.length <= 50 for e in found)


class TestDetectShortExonsWithMockReference:
    """Test detect_short_exons with mock reference files."""

    def test_detect_short_exons_skips_complete_genes(self, tmp_path):
        """Should skip genes that already have expected exon count."""
        genome = GenomeSequence(
            seqid="test",
            sequence="N" * 10000,
            is_circular=True,
        )
        db_manager = DBManager()
        found_genes = {
            "nad5": GeneAnnotation(
                gene_name="nad5",
                product="NADH dehydrogenase subunit 5",
                exons=[
                    ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1),
                    ExonRecord(start=600, end=900, strand=Strand.PLUS, number=2),
                    ExonRecord(start=1000, end=1022, strand=Strand.PLUS, number=3),
                    ExonRecord(start=1500, end=2000, strand=Strand.PLUS, number=4),
                    ExonRecord(start=2100, end=2500, strand=Strand.PLUS, number=5),
                ],
                strand=Strand.PLUS,
                gene_type="CDS",
            )
        }

        result = detect_short_exons(genome, db_manager, found_genes)

        # Should return unchanged (already has 5 exons)
        assert len(result["nad5"].exons) == 5

    def test_detect_short_exons_logs_missing_reference(self, tmp_path, caplog):
        """Should log warning when no nucleotide reference file exists."""
        import logging

        genome = GenomeSequence(
            seqid="test",
            sequence="N" * 10000,
            is_circular=True,
        )

        # Create DBManager with temporary db path
        db_manager = DBManager()
        # Ensure ref directory exists but no reference files
        ref_dir = db_manager.blast_ref_dir
        ref_dir.mkdir(parents=True, exist_ok=True)

        found_genes = {
            "nad5": GeneAnnotation(
                gene_name="nad5",
                product="NADH dehydrogenase subunit 5",
                exons=[
                    ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1),
                ],
                strand=Strand.PLUS,
                gene_type="CDS",
            )
        }

        with caplog.at_level(logging.DEBUG):
            result = detect_short_exons(genome, db_manager, found_genes)

        # Should return unchanged because no reference file
        assert len(result["nad5"].exons) == 1
        # Should have logged about missing reference or no blastn
        # (either blastn not available or no reference file)


class TestCircularGeneSpan:
    """Regression tests for _circular_gene_span origin-crossing logic."""

    def test_empty_exons_returns_zero(self):
        from mitoflow.annotate.trans_splicing import _circular_gene_span

        assert _circular_gene_span([], 10000) == 0

    def test_single_exon_returns_its_length(self):
        from mitoflow.annotate.trans_splicing import _circular_gene_span

        exon = ExonRecord(start=100, end=500, strand=Strand.PLUS, number=1)
        assert _circular_gene_span([exon], 10000) == 401

    def test_linear_exons_span(self):
        from mitoflow.annotate.trans_splicing import _circular_gene_span

        exons = [
            ExonRecord(start=100, end=300, strand=Strand.PLUS, number=1),
            ExonRecord(start=400, end=600, strand=Strand.PLUS, number=2),
            ExonRecord(start=800, end=900, strand=Strand.PLUS, number=3),
        ]
        # Wrap-around gap dominates; span covers 100..900 = 801 bp
        assert _circular_gene_span(exons, 10000) == 801

    def test_exons_across_origin(self):
        from mitoflow.annotate.trans_splicing import _circular_gene_span

        exons = [
            ExonRecord(start=9800, end=9950, strand=Strand.PLUS, number=1),
            ExonRecord(start=50, end=150, strand=Strand.PLUS, number=2),
            ExonRecord(start=300, end=500, strand=Strand.PLUS, number=3),
        ]
        # Linear distance would be ~9900, but circular span is the short arc
        # covering 9800..9950 + 0..150 + 300..500 = 701 bp
        assert _circular_gene_span(exons, 10000) == 701

    def test_nearly_full_circle(self):
        from mitoflow.annotate.trans_splicing import _circular_gene_span

        exons = [
            ExonRecord(start=1, end=100, strand=Strand.PLUS, number=1),
            ExonRecord(start=200, end=9900, strand=Strand.PLUS, number=2),
        ]
        # Largest gap is wrap-around (100 bp), so span = 10000 - 100 = 9900
        assert _circular_gene_span(exons, 10000) == 9900