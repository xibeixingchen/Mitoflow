"""Tests for CMS benchmark utilities."""

from __future__ import annotations

from mitoflow.cms.benchmark.dataset import (
    load_positive_samples,
    generate_shuffled_negatives,
    generate_random_orf_negatives,
    build_full_dataset,
)
from mitoflow.cms.benchmark.synthetic_genomes import build_synthetic_genome


def test_load_positives_returns_cms_samples():
    positives = load_positive_samples()
    assert len(positives) > 0
    assert all(p.label == 1 for p in positives)
    assert all(p.source_type == "cms_positive" for p in positives)


def test_shuffled_negatives_are_distinct():
    positives = load_positive_samples()[:3]
    negatives = generate_shuffled_negatives(positives, n_per_sample=2)
    assert len(negatives) == 6
    assert all(n.label == 0 for n in negatives)
    for p in positives:
        related = [n for n in negatives if n.metadata.get("parent") == p.sample_id]
        assert len(related) == 2
        for r in related:
            assert r.protein_seq != p.protein_seq


def test_random_orf_negatives_valid():
    negs = generate_random_orf_negatives(n_samples=5)
    assert len(negs) == 5
    assert all(n.label == 0 for n in negs)
    assert all(n.nt_seq.startswith("ATG") for n in negs)
    assert all(len(n.nt_seq) >= 300 for n in negs)


def test_build_full_dataset_balanced():
    dataset = build_full_dataset(n_shuffled=1, n_pcg=10, n_random=10, seed=42)
    positives = [d for d in dataset if d.label == 1]
    negatives = [d for d in dataset if d.label == 0]
    assert len(positives) > 0
    assert len(negatives) == len(positives) + 10 + 10


def test_synthetic_genome_length():
    from mitoflow.cms.benchmark.dataset import CMSTestSample
    sample = CMSTestSample(
        sample_id="test",
        label=1,
        protein_seq="M" * 100,
        nt_seq="ATG" + "AAA" * 99,
        source_type="test",
        metadata={},
    )
    genome_seq, annotations, test_coords = build_synthetic_genome(sample)
    assert len(genome_seq) > len(sample.nt_seq)
    assert len(annotations) == 4
    gene_names = {a.gene_name for a in annotations}
    assert gene_names == {"atp6", "cox1", "nad5", "cob"}
    assert test_coords[0] > 0
    assert test_coords[1] >= test_coords[0]
