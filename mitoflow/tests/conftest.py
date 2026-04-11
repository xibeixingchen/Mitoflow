"""Shared test fixtures for MitoFlow tests."""

import pytest
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


@pytest.fixture
def tiny_mito_fasta(tmp_path):
    """Create a tiny synthetic mitochondrial FASTA for testing."""
    seq = "ATG" + "GCN" * 100 + "ATG" + "GCN" * 200 + "TAA" + "N" * 200
    # ~1200 bp with two "genes"
    fasta_path = tmp_path / "test_mito.fasta"
    record = SeqRecord(Seq(seq), id="test_contig1", description="test mitochondrion")
    SeqIO.write(record, str(fasta_path), "fasta")
    return fasta_path


@pytest.fixture
def multi_contig_fasta(tmp_path):
    """Create a multi-contig FASTA for testing merge logic."""
    fasta_path = tmp_path / "test_multicontig.fasta"
    records = [
        SeqRecord(Seq("ATGCGN" * 50), id="contig1", description=""),
        SeqRecord(Seq("ATGCGN" * 30), id="contig2", description=""),
        SeqRecord(Seq("ATGCGN" * 20), id="contig3", description=""),
    ]
    SeqIO.write(records, str(fasta_path), "fasta")
    return fasta_path
