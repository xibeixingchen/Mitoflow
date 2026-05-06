"""Tests for trans-spliced gene exon merging."""

import pytest
from pathlib import Path

from mitoflow.annotate.trans_splicing import (
    parse_exon_id,
    merge_exons_to_gene,
    TRANS_SPLICED_CONFIG,
)
from mitoflow.models.gene import GeneAnnotation, ExonRecord, Strand
from mitoflow.models.genome import GenomeSequence


def _create_mock_genome(length: int = 1000000) -> GenomeSequence:
    """Create a mock genome for testing."""
    return GenomeSequence(
        seqid="mock_genome",
        sequence="A" * length,  # Simple mock sequence
        is_circular=True,
    )


def test_parse_exon_id():
    """Test parsing exon ID from PMGA format."""
    # Standard PMGA format
    exon_id = "ArthCpNC-037304_cds181_nad5_1_230"
    gene, num, length = parse_exon_id(exon_id)

    assert gene == "nad5"
    assert num == 1
    assert length == 230

    # Another example
    exon_id = "GlmaCpNC-020455_cds183_nad5_3_22"
    gene, num, length = parse_exon_id(exon_id)

    assert gene == "nad5"
    assert num == 3
    assert length == 22


def test_parse_exon_id_various_formats():
    """Test parsing various exon ID formats."""
    # Simple format: gene_num_length
    exon_id = "refCp_cds46_rps12_2_232"
    gene, num, length = parse_exon_id(exon_id)
    assert gene == "rps12"
    assert num == 2
    assert length == 232

    # Another complex prefix
    exon_id = "species_v1_gene_nad1_5_100"
    gene, num, length = parse_exon_id(exon_id)
    assert gene == "nad1"
    assert num == 5
    assert length == 100


def test_parse_exon_id_invalid():
    """Test that invalid exon IDs return None."""
    # Too few parts
    assert parse_exon_id("invalid") is None
    assert parse_exon_id("nad5_1") is None

    # Non-numeric parts
    assert parse_exon_id("prefix_gene_abc_xyz") is None


def test_merge_exons_to_gene_complete():
    """Test merging exons when all exons are found."""
    genome = _create_mock_genome()
    # Simulate finding all 5 nad5 exons
    # Format: (start, end, strand, identity, hit_length, expected_length)
    exon_hits = {
        1: [(1000, 1230, Strand.PLUS, 100.0, 230, 230)],
        2: [(5000, 6216, Strand.PLUS, 98.5, 1216, 1216)],
        3: [(10000, 10022, Strand.PLUS, 100.0, 22, 22)],
        4: [(20000, 20395, Strand.PLUS, 95.0, 395, 395)],
        5: [(30000, 30147, Strand.PLUS, 99.0, 147, 147)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config, genome)

    assert result is not None
    assert result.gene_name == "nad5"
    assert result.genomic_start == 1000  # min start
    assert result.genomic_end == 30147  # max end
    assert len(result.exons) == 5


def test_merge_exons_to_gene_incomplete():
    """Test that merging fails when exons are incomplete."""
    genome = _create_mock_genome()
    # Only found 3 of 5 exons
    exon_hits = {
        1: [(1000, 1230, Strand.PLUS, 100.0, 230, 230)],
        3: [(10000, 10022, Strand.PLUS, 100.0, 22, 22)],
        5: [(30000, 30147, Strand.PLUS, 99.0, 147, 147)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config, genome)

    assert result is None  # Cannot merge incomplete


def test_merge_exons_span_exceeds_max():
    """Test that merging fails when span exceeds max."""
    genome = _create_mock_genome(2000000)
    # Exons too far apart for cox2 (max_span=200000)
    exon_hits = {
        1: [(1000, 1800, Strand.PLUS, 100.0, 800, 800)],
        2: [(600000, 615000, Strand.PLUS, 98.5, 1500, 1500)],  # Too far! (span = 614000 > max_span=200000)
    }

    config = TRANS_SPLICED_CONFIG["cox2"]  # max_span=200000
    result = merge_exons_to_gene("cox2", exon_hits, config, genome)

    assert result is None  # Span exceeds max


def test_merge_exons_selects_best_hit():
    """Test that merging selects the best hit when multiple hits per exon."""
    genome = _create_mock_genome()
    # Multiple hits for exon 1, should select full-length match (coverage >= 0.9)
    exon_hits = {
        1: [
            (1000, 1230, Strand.PLUS, 90.0, 230, 230),  # Full-length, 90% identity
            (2000, 2100, Strand.PLUS, 100.0, 100, 230),  # Partial (43%), 100% identity - should NOT be selected
        ],
        2: [(5000, 6216, Strand.PLUS, 98.5, 1216, 1216)],
        3: [(10000, 10022, Strand.PLUS, 100.0, 22, 22)],
        4: [(20000, 20395, Strand.PLUS, 95.0, 395, 395)],
        5: [(30000, 30147, Strand.PLUS, 99.0, 147, 147)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config, genome)

    assert result is not None
    # Exon 1 should be at position 1000-1230 (full-length match preferred)
    assert result.exons[0].start == 1000
    assert result.exons[0].end == 1230


def test_merge_exons_minus_strand():
    """Test merging exons on minus strand."""
    genome = _create_mock_genome()
    # All exons on minus strand
    exon_hits = {
        1: [(30000, 30147, Strand.MINUS, 99.0, 147, 147)],
        2: [(20000, 20395, Strand.MINUS, 95.0, 395, 395)],
        3: [(10000, 10022, Strand.MINUS, 100.0, 22, 22)],
        4: [(5000, 6216, Strand.MINUS, 98.5, 1216, 1216)],
        5: [(1000, 1230, Strand.MINUS, 100.0, 230, 230)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config, genome)

    assert result is not None
    assert result.strand == Strand.MINUS
    assert len(result.exons) == 5


def test_merge_exons_renumbers_correctly():
    """Test that exons are renumbered by genomic position after merge."""
    genome = _create_mock_genome()
    # Exons given out of genomic order
    exon_hits = {
        5: [(30000, 30147, Strand.PLUS, 99.0, 147, 147)],  # Last in genome
        1: [(1000, 1230, Strand.PLUS, 100.0, 230, 230)],   # First in genome
        3: [(10000, 10022, Strand.PLUS, 100.0, 22, 22)],  # Middle
        2: [(5000, 6216, Strand.PLUS, 98.5, 1216, 1216)],    # Second
        4: [(20000, 20395, Strand.PLUS, 95.0, 395, 395)],  # Fourth
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config, genome)

    assert result is not None
    # Exons should be sorted by position and numbered 1-5
    assert result.exons[0].number == 1
    assert result.exons[0].start == 1000
    assert result.exons[1].number == 2
    assert result.exons[1].start == 5000
    assert result.exons[2].number == 3
    assert result.exons[2].start == 10000
    assert result.exons[3].number == 4
    assert result.exons[3].start == 20000
    assert result.exons[4].number == 5
    assert result.exons[4].start == 30000


def test_merge_exons_nad1():
    """Test merging exons for nad1 (5 exons)."""
    genome = _create_mock_genome()
    # nad1 expected: 300-380aa (mid 340), so ~1020bp total CDS needed
    exon_hits = {
        1: [(5000, 5060, Strand.PLUS, 99.0, 61, 61)],
        2: [(15000, 15600, Strand.PLUS, 98.0, 601, 601)],
        3: [(25000, 25030, Strand.PLUS, 100.0, 31, 31)],
        4: [(35000, 35150, Strand.PLUS, 97.0, 151, 151)],
        5: [(45000, 45100, Strand.PLUS, 99.0, 101, 101)],
    }

    config = TRANS_SPLICED_CONFIG["nad1"]
    result = merge_exons_to_gene("nad1", exon_hits, config, genome)

    assert result is not None
    assert result.gene_name == "nad1"
    assert len(result.exons) == 5


def test_merge_exons_nad4():
    """Test merging exons for nad4 (4 exons)."""
    genome = _create_mock_genome()
    # nad4 expected: 430-520aa (mid 475), so ~1425bp total CDS needed
    exon_hits = {
        1: [(10000, 10450, Strand.PLUS, 99.0, 451, 451)],
        2: [(20000, 20500, Strand.PLUS, 98.0, 501, 501)],
        3: [(30000, 30150, Strand.PLUS, 100.0, 151, 151)],
        4: [(40000, 40500, Strand.PLUS, 97.0, 501, 501)],
    }

    config = TRANS_SPLICED_CONFIG["nad4"]
    result = merge_exons_to_gene("nad4", exon_hits, config, genome)

    assert result is not None
    assert result.gene_name == "nad4"
    assert len(result.exons) == 4


def test_merge_exons_cox2():
    """Test merging exons for cox2 (2 exons)."""
    genome = _create_mock_genome()
    # cox2 expected: 220-280aa (mid 250), so ~750bp total CDS needed
    exon_hits = {
        1: [(5000, 5250, Strand.PLUS, 100.0, 251, 251)],
        2: [(10000, 10500, Strand.PLUS, 98.5, 501, 501)],
    }

    config = TRANS_SPLICED_CONFIG["cox2"]
    result = merge_exons_to_gene("cox2", exon_hits, config, genome)

    assert result is not None
    assert result.gene_name == "cox2"
    assert len(result.exons) == 2


def test_trans_spliced_config_values():
    """Test TRANS_SPLICED_CONFIG has expected values."""
    assert "nad1" in TRANS_SPLICED_CONFIG
    assert "nad2" in TRANS_SPLICED_CONFIG
    assert "nad5" in TRANS_SPLICED_CONFIG
    assert "nad4" in TRANS_SPLICED_CONFIG
    assert "nad7" in TRANS_SPLICED_CONFIG
    assert "cox2" in TRANS_SPLICED_CONFIG
    assert "rps3" in TRANS_SPLICED_CONFIG
    assert "cox1" in TRANS_SPLICED_CONFIG

    # Check nad5 has expected config (updated to support large genomes like Cucumis)
    assert TRANS_SPLICED_CONFIG["nad5"]["exons"] == 5
    assert TRANS_SPLICED_CONFIG["nad5"]["max_span"] == 2000000  # Updated from 500000 for large genomes
    assert TRANS_SPLICED_CONFIG["nad5"]["min_exon_bp"] == 20

    # Check nad1 has expected config (also updated for large genomes)
    assert TRANS_SPLICED_CONFIG["nad1"]["exons"] == 5
    assert TRANS_SPLICED_CONFIG["nad1"]["max_span"] == 1500000

    # Check nad4 has 4 exons
    assert TRANS_SPLICED_CONFIG["nad4"]["exons"] == 4

    # Check cox2 has 2 exons
    assert TRANS_SPLICED_CONFIG["cox2"]["exons"] == 2

    # Check rps3 has limited max_exon_gap to prevent false positives
    assert TRANS_SPLICED_CONFIG["rps3"]["max_exon_gap"] == 50000

    # Check cox1 config
    assert TRANS_SPLICED_CONFIG["cox1"]["exons"] == 2
    assert TRANS_SPLICED_CONFIG["cox1"]["max_span"] == 200000