"""Tests for trans-spliced gene exon merging."""

import pytest
from pathlib import Path

from mitoflow.annotate.trans_splicing import (
    parse_exon_id,
    merge_exons_to_gene,
    TRANS_SPLICED_CONFIG,
)
from mitoflow.models.gene import GeneAnnotation, ExonRecord, Strand


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
    # Simulate finding all 5 nad5 exons
    exon_hits = {
        1: [(1000, 1230, Strand.PLUS, 100.0)],
        2: [(5000, 6216, Strand.PLUS, 98.5)],
        3: [(10000, 10022, Strand.PLUS, 100.0)],
        4: [(20000, 20395, Strand.PLUS, 95.0)],
        5: [(30000, 30147, Strand.PLUS, 99.0)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config)

    assert result is not None
    assert result.gene_name == "nad5"
    assert result.genomic_start == 1000  # min start
    assert result.genomic_end == 30147  # max end
    assert len(result.exons) == 5


def test_merge_exons_to_gene_incomplete():
    """Test that merging fails when exons are incomplete."""
    # Only found 3 of 5 exons
    exon_hits = {
        1: [(1000, 1230, Strand.PLUS, 100.0)],
        3: [(10000, 10022, Strand.PLUS, 100.0)],
        5: [(30000, 30147, Strand.PLUS, 99.0)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config)

    assert result is None  # Cannot merge incomplete


def test_merge_exons_span_exceeds_max():
    """Test that merging fails when span exceeds max."""
    # Exons too far apart
    exon_hits = {
        1: [(1000, 1230, Strand.PLUS, 100.0)],
        2: [(600000, 601216, Strand.PLUS, 98.5)],  # Too far!
        3: [(700000, 700022, Strand.PLUS, 100.0)],
        4: [(800000, 800395, Strand.PLUS, 95.0)],
        5: [(900000, 900147, Strand.PLUS, 99.0)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]  # max_span=500000
    result = merge_exons_to_gene("nad5", exon_hits, config)

    assert result is None  # Span exceeds max


def test_merge_exons_selects_best_hit():
    """Test that merging selects the best hit when multiple hits per exon."""
    # Multiple hits for exon 1, should select highest identity
    exon_hits = {
        1: [
            (1000, 1230, Strand.PLUS, 90.0),  # Lower identity
            (2000, 2230, Strand.PLUS, 100.0),  # Higher identity - should be selected
        ],
        2: [(5000, 6216, Strand.PLUS, 98.5)],
        3: [(10000, 10022, Strand.PLUS, 100.0)],
        4: [(20000, 20395, Strand.PLUS, 95.0)],
        5: [(30000, 30147, Strand.PLUS, 99.0)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config)

    assert result is not None
    # Exon 1 should be at position 2000-2230 (best hit)
    assert result.exons[0].start == 2000
    assert result.exons[0].end == 2230


def test_merge_exons_minus_strand():
    """Test merging exons on minus strand."""
    # All exons on minus strand
    exon_hits = {
        1: [(30147, 30000, Strand.MINUS, 99.0)],  # Note: start > end for minus strand
        2: [(20395, 20000, Strand.MINUS, 95.0)],
        3: [(10022, 10000, Strand.MINUS, 100.0)],
        4: [(6216, 5000, Strand.MINUS, 98.5)],
        5: [(1230, 1000, Strand.MINUS, 100.0)],
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config)

    assert result is not None
    assert result.strand == Strand.MINUS
    assert len(result.exons) == 5


def test_merge_exons_renumbers_correctly():
    """Test that exons are renumbered by genomic position after merge."""
    # Exons given out of genomic order
    exon_hits = {
        5: [(30000, 30147, Strand.PLUS, 99.0)],  # Last in genome
        1: [(1000, 1230, Strand.PLUS, 100.0)],   # First in genome
        3: [(10000, 10022, Strand.PLUS, 100.0)],  # Middle
        2: [(5000, 6216, Strand.PLUS, 98.5)],    # Second
        4: [(20000, 20395, Strand.PLUS, 95.0)],  # Fourth
    }

    config = TRANS_SPLICED_CONFIG["nad5"]
    result = merge_exons_to_gene("nad5", exon_hits, config)

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
    exon_hits = {
        1: [(5000, 5200, Strand.PLUS, 99.0)],
        2: [(15000, 16200, Strand.PLUS, 98.0)],
        3: [(25000, 25150, Strand.PLUS, 100.0)],  # Short exon
        4: [(35000, 35300, Strand.PLUS, 97.0)],
        5: [(45000, 45100, Strand.PLUS, 99.0)],
    }

    config = TRANS_SPLICED_CONFIG["nad1"]
    result = merge_exons_to_gene("nad1", exon_hits, config)

    assert result is not None
    assert result.gene_name == "nad1"
    assert len(result.exons) == 5


def test_merge_exons_nad4():
    """Test merging exons for nad4 (4 exons)."""
    exon_hits = {
        1: [(10000, 11500, Strand.PLUS, 99.0)],
        2: [(20000, 21500, Strand.PLUS, 98.0)],
        3: [(30000, 30500, Strand.PLUS, 100.0)],
        4: [(40000, 42000, Strand.PLUS, 97.0)],
    }

    config = TRANS_SPLICED_CONFIG["nad4"]
    result = merge_exons_to_gene("nad4", exon_hits, config)

    assert result is not None
    assert result.gene_name == "nad4"
    assert len(result.exons) == 4


def test_merge_exons_cox2():
    """Test merging exons for cox2 (2 exons)."""
    exon_hits = {
        1: [(5000, 5800, Strand.PLUS, 100.0)],
        2: [(10000, 11500, Strand.PLUS, 98.5)],
    }

    config = TRANS_SPLICED_CONFIG["cox2"]
    result = merge_exons_to_gene("cox2", exon_hits, config)

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

    # Check nad5 has expected config
    assert TRANS_SPLICED_CONFIG["nad5"]["exons"] == 5
    assert TRANS_SPLICED_CONFIG["nad5"]["max_span"] == 500000
    assert TRANS_SPLICED_CONFIG["nad5"]["min_exon_bp"] == 20

    # Check nad1 has expected config
    assert TRANS_SPLICED_CONFIG["nad1"]["exons"] == 5

    # Check nad4 has 4 exons
    assert TRANS_SPLICED_CONFIG["nad4"]["exons"] == 4

    # Check cox2 has 2 exons
    assert TRANS_SPLICED_CONFIG["cox2"]["exons"] == 2