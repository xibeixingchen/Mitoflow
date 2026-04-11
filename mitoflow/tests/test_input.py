"""Tests for FASTA input handling."""

from mitoflow.core.input import load_fasta, validate_fasta


def test_load_single_contig(tiny_mito_fasta):
    """Test loading a single-contig FASTA."""
    genome = load_fasta(tiny_mito_fasta)
    assert genome.seqid == "test_contig1"
    assert len(genome.sequence) > 0
    assert genome.gc_content > 0
    assert genome.contig_map is None  # Single contig, no map needed


def test_load_multi_contig(multi_contig_fasta):
    """Test merging multi-contig FASTA."""
    genome = load_fasta(multi_contig_fasta)
    assert genome.contig_map is not None
    assert len(genome.contig_map) == 3
    assert genome.contig_map[0].original_id == "contig1"
    # Check gap between contigs (200 N's)
    assert "N" * 200 in genome.sequence


def test_gc_content(tiny_mito_fasta):
    """Test GC content calculation."""
    genome = load_fasta(tiny_mito_fasta)
    gc = genome.gc_content
    assert 0 < gc < 100


def test_validate_fasta(tiny_mito_fasta):
    """Test FASTA validation produces warnings."""
    genome = load_fasta(tiny_mito_fasta)
    warnings = validate_fasta(genome)
    # Short sequence should produce a warning
    assert len(genome.sequence) < 10_000
    assert any("short" in w.lower() for w in warnings)


def test_load_nonexistent_file():
    """Test that loading a non-existent file raises error."""
    import pytest
    with pytest.raises(FileNotFoundError):
        load_fasta("/nonexistent/path.fasta")


def test_reverse_complement(tiny_mito_fasta):
    """Test reverse complement."""
    genome = load_fasta(tiny_mito_fasta)
    rc = genome.reverse_complement
    assert len(rc) == len(genome.sequence)
    # Check first/last bases complement
    comp = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
    if genome.sequence[0] in comp:
        assert rc[-1] == comp[genome.sequence[0]]
