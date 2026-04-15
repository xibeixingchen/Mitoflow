"""Synthetic genome construction for CMS benchmark.

Each test sample is embedded into a small circular 'genome' with flanking
mock genes so that predict_cms() can run with full context analysis.
"""

from __future__ import annotations

import logging
import random

from ...models.gene import GeneAnnotation, ExonRecord, Strand
from .dataset import CMSTestSample

logger = logging.getLogger(__name__)

# Typical lengths for flanking mock genes (bp)
_FLANK_GENE_ORDER = [
    ("atp6", 1500),
    ("cox1", 1600),
    ("nad5", 2000),
    ("cob", 1200),
]

# Safe DNA unit: no ATG, no STOP codons in any frame shift
_SAFE_UNIT = "ACGACG"


def _safe_dna(length: int, rng: random.Random) -> str:
    """Generate DNA without ATG or stop codons to avoid spurious ORFs."""
    base = _SAFE_UNIT * (length // len(_SAFE_UNIT) + 2)
    return base[:length]


def build_synthetic_genome(
    sample: CMSTestSample,
    intergenic_spacer: int = 300,
    seed: int = 42,
) -> tuple[str, list[GeneAnnotation], tuple[int, int]]:
    """Build a synthetic FASTA and annotations for one test sample.

    Layout (circular):
        [atp6] --spacer-- [TEST_ORF] --spacer-- [cox1] --spacer-- [nad5] --spacer-- [cob] --spacer--

    Returns:
        genome_sequence: the full DNA string
        annotated_genes: list of GeneAnnotation for the flanking genes only
        test_orf_coords: (start, end) 1-based inclusive coordinates of the embedded test ORF
    """
    test_nt = sample.nt_seq.upper()
    if len(test_nt) < 300:
        test_nt += "N" * (300 - len(test_nt))

    rng = random.Random(seed)

    # Build segments: gene, spacer, gene, spacer, ...
    segments: list[tuple[str | None, str]] = []  # (gene_name or None, sequence)
    for gname, glen in _FLANK_GENE_ORDER:
        segments.append((gname, _safe_dna(glen, rng)))
        segments.append((None, "N" * intergenic_spacer))

    # Insert test ORF between atp6 and cox1 (after first spacer, index 1)
    # Current segments: atp6, spacer, cox1, spacer, nad5, spacer, cob, spacer
    # Insert: spacer + test ORF + STOP codon + spacer
    # The STOP ensures _scan_orfs terminates the ORF correctly.
    segments.insert(2, (None, "N" * intergenic_spacer))
    segments.insert(3, ("TEST_ORF", test_nt + "TAA"))

    # Assemble genome and annotate flanking genes
    genome_seq = ""
    annotated_genes: list[GeneAnnotation] = []
    test_orf_coords: tuple[int, int] = (0, 0)
    cursor = 1
    for name, seq in segments:
        seg_start = cursor
        seg_end = cursor + len(seq) - 1
        if name is not None and name != "TEST_ORF":
            annotated_genes.append(
                GeneAnnotation(
                    gene_name=name,
                    exons=[
                        ExonRecord(
                            start=seg_start,
                            end=seg_end,
                            strand=Strand.PLUS,
                            number=1,
                        )
                    ],
                    strand=Strand.PLUS,
                )
            )
        elif name == "TEST_ORF":
            test_orf_coords = (seg_start, seg_end)
        genome_seq += seq
        cursor = seg_end + 1

    return genome_seq, annotated_genes, test_orf_coords
