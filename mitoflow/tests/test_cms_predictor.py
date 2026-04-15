"""Tests for CMS predictor core logic."""

from __future__ import annotations

import pytest

from mitoflow.cms.predictor import _scan_orfs, _translate, _score_candidate, predict_cms, CMSCandidate


def test_scan_orfs_finds_atg_initiated_orfs():
    seq = "ATG" + "A" * 297 + "TAA"  # 303 bp ORF
    orfs = _scan_orfs(seq, min_length=300)
    assert len(orfs) == 1
    start, end, strand, nt = orfs[0]
    assert strand == 1
    assert end - start + 1 == 303


def test_translate_produces_correct_protein():
    assert _translate("ATGGGGTAA") == "MG*"
    assert _translate("ATGAAATAA") == "MK*"


def test_score_candidate_range():
    cand = CMSCandidate(
        orf_id="test1",
        start=1,
        end=300,
        strand=1,
        length_bp=300,
        length_aa=100,
        protein_seq="M" * 100,
        nt_seq="ATG" + "AAA" * 99,
    )
    _score_candidate(cand)
    assert 0.0 <= cand.total_score <= 100.0
    assert cand.confidence in ("High", "Medium", "Low")


def test_predict_cms_empty_genome():
    from pathlib import Path
    import tempfile
    from mitoflow.cms.predictor import CMSResult

    with tempfile.TemporaryDirectory() as tmpdir:
        fasta = Path(tmpdir) / "empty.fasta"
        fasta.write_text(">test\nATGTAATAA\n")
        result = predict_cms(
            fasta_path=fasta,
            genome_seq="ATGTAATAA",
            annotated_genes=[],
            min_orf_length=300,
        )
        assert isinstance(result, CMSResult)
        assert result.n_candidates == 0
