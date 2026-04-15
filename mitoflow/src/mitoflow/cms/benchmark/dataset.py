"""Construct validation datasets for CMS predictor benchmarking.

Positives: known CMS genes from cms_proteins.fasta.
Negatives: shuffled CMS sequences, known mitochondrial PCGs, and random ORFs.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from Bio import SeqIO

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "cms"
BLAST_REFS_DIR = Path(__file__).parent.parent.parent / "data" / "blast_refs" / "pcg"


@dataclass
class CMSTestSample:
    """A single test sample for CMS benchmark."""

    sample_id: str
    label: int  # 1 = CMS positive, 0 = negative
    protein_seq: str
    nt_seq: str
    source_type: str  # e.g. "cms_positive", "shuffled", "pcg", "random_orf"
    metadata: dict


def _load_fasta_sequences(fasta_path: Path) -> list[tuple[str, str]]:
    """Load (header, sequence) pairs from a FASTA file."""
    records = []
    for rec in SeqIO.parse(str(fasta_path), "fasta"):
        records.append((rec.description, str(rec.seq)))
    return records


def load_positive_samples(max_length: int = 2000) -> list[CMSTestSample]:
    """Load curated CMS proteins as positive samples."""
    fasta_path = DATA_DIR / "cms_proteins.fasta"
    if not fasta_path.exists():
        raise FileNotFoundError(f"CMS reference FASTA not found: {fasta_path}")

    samples: list[CMSTestSample] = []
    for header, seq in _load_fasta_sequences(fasta_path):
        name = header.split()[0] if header else "unknown"
        if len(seq) > max_length:
            continue
        # Back-translate protein to a synthetic coding sequence using common codons
        nt_seq = _protein_to_dna(seq)
        samples.append(
            CMSTestSample(
                sample_id=name,
                label=1,
                protein_seq=seq,
                nt_seq=nt_seq,
                source_type="cms_positive",
                metadata={"header": header},
            )
        )
    logger.info("Loaded %d CMS positive samples", len(samples))
    return samples


def generate_shuffled_negatives(
    positive_samples: list[CMSTestSample],
    n_per_sample: int = 1,
    seed: int = 42,
) -> list[CMSTestSample]:
    """Generate negative samples by shuffling amino-acid sequences."""
    rng = random.Random(seed)
    negatives: list[CMSTestSample] = []
    for ps in positive_samples:
        for i in range(n_per_sample):
            shuffled_aa = list(ps.protein_seq)
            rng.shuffle(shuffled_aa)
            shuffled_seq = "".join(shuffled_aa)
            nt_seq = _protein_to_dna(shuffled_seq)
            negatives.append(
                CMSTestSample(
                    sample_id=f"{ps.sample_id}_shuf_{i + 1}",
                    label=0,
                    protein_seq=shuffled_seq,
                    nt_seq=nt_seq,
                    source_type="shuffled",
                    metadata={"parent": ps.sample_id},
                )
            )
    logger.info("Generated %d shuffled negatives", len(negatives))
    return negatives


def load_pcg_negatives(
    n_samples: int = 100,
    min_length: int = 50,
    max_length: int = 800,
    seed: int = 42,
) -> list[CMSTestSample]:
    """Sample known mitochondrial protein-coding genes as negatives."""
    rng = random.Random(seed)
    all_records: list[tuple[str, str]] = []

    if not BLAST_REFS_DIR.exists():
        logger.warning("BLAST refs PCG directory not found: %s", BLAST_REFS_DIR)
        return []

    for fasta_file in BLAST_REFS_DIR.glob("*.fasta"):
        try:
            for header, seq in _load_fasta_sequences(fasta_file):
                if min_length <= len(seq) <= max_length:
                    all_records.append((header, seq))
        except Exception as e:
            logger.debug("Failed to parse %s: %s", fasta_file, e)

    if not all_records:
        logger.warning("No PCG records found for negatives")
        return []

    rng.shuffle(all_records)
    selected = all_records[:n_samples]
    samples: list[CMSTestSample] = []
    for header, seq in selected:
        name = header.split()[0] if header else "unknown"
        nt_seq = _protein_to_dna(seq)
        samples.append(
            CMSTestSample(
                sample_id=f"pcg_{name}",
                label=0,
                protein_seq=seq,
                nt_seq=nt_seq,
                source_type="pcg",
                metadata={"header": header},
            )
        )
    logger.info("Loaded %d PCG negatives", len(samples))
    return samples


def generate_random_orf_negatives(
    n_samples: int = 100,
    orf_length_range: tuple[int, int] = (300, 1500),
    seed: int = 42,
) -> list[CMSTestSample]:
    """Generate random ATG-initiated ORFs as negatives.

    These are synthetic sequences with random codons, started with ATG and
    terminated with a stop codon. They have no biological signal.
    """
    rng = random.Random(seed)
    codons = [
        "TTT", "TTC", "TTA", "TTG", "CTT", "CTC", "CTA", "CTG",
        "ATT", "ATC", "ATA", "ATG", "GTT", "GTC", "GTA", "GTG",
        "TCT", "TCC", "TCA", "TCG", "CCT", "CCC", "CCA", "CCG",
        "ACT", "ACC", "ACA", "ACG", "GCT", "GCC", "GCA", "GCG",
        "TAT", "TAC", "CAT", "CAC", "CAA", "CAG", "AAT", "AAC",
        "AAA", "AAG", "GAT", "GAC", "GAA", "GAG", "TGT", "TGC",
        "TGG", "CGT", "CGC", "CGA", "CGG", "AGT", "AGC", "AGA",
        "AGG", "GGT", "GGC", "GGA", "GGG",
    ]
    stop_codons = ["TAA", "TAG", "TGA"]
    # Exclude stops from body codons
    body_codons = [c for c in codons if c not in stop_codons]

    samples: list[CMSTestSample] = []
    for i in range(n_samples):
        length_bp = rng.randint(orf_length_range[0], orf_length_range[1])
        # Ensure length is multiple of 3
        length_bp -= length_bp % 3
        n_codons = length_bp // 3
        codon_seq = ["ATG"] + [rng.choice(body_codons) for _ in range(n_codons - 2)] + [rng.choice(stop_codons)]
        nt_seq = "".join(codon_seq)
        protein_seq = _translate(nt_seq)
        samples.append(
            CMSTestSample(
                sample_id=f"random_orf_{i + 1}",
                label=0,
                protein_seq=protein_seq,
                nt_seq=nt_seq,
                source_type="random_orf",
                metadata={"length_bp": length_bp},
            )
        )
    logger.info("Generated %d random ORF negatives", len(samples))
    return samples


def build_full_dataset(
    n_shuffled: int = 1,
    n_pcg: int = 100,
    n_random: int = 100,
    seed: int = 42,
) -> list[CMSTestSample]:
    """Build the complete benchmark dataset."""
    positives = load_positive_samples()
    negatives = []
    negatives.extend(generate_shuffled_negatives(positives, n_per_sample=n_shuffled, seed=seed))
    negatives.extend(load_pcg_negatives(n_samples=n_pcg, seed=seed))
    negatives.extend(generate_random_orf_negatives(n_samples=n_random, seed=seed))
    return positives + negatives


# ── Helpers ─────────────────────────────────────────────────────────

_CODON_TABLE = {
    "F": ["TTT", "TTC"],
    "L": ["TTA", "TTG", "CTT", "CTC", "CTA", "CTG"],
    "I": ["ATT", "ATC", "ATA"],
    "M": ["ATG"],
    "V": ["GTT", "GTC", "GTA", "GTG"],
    "S": ["TCT", "TCC", "TCA", "TCG", "AGT", "AGC"],
    "P": ["CCT", "CCC", "CCA", "CCG"],
    "T": ["ACT", "ACC", "ACA", "ACG"],
    "A": ["GCT", "GCC", "GCA", "GCG"],
    "Y": ["TAT", "TAC"],
    "*": ["TAA", "TAG", "TGA"],
    "H": ["CAT", "CAC"],
    "Q": ["CAA", "CAG"],
    "N": ["AAT", "AAC"],
    "K": ["AAA", "AAG"],
    "D": ["GAT", "GAC"],
    "E": ["GAA", "GAG"],
    "C": ["TGT", "TGC"],
    "W": ["TGG"],
    "R": ["CGT", "CGC", "CGA", "CGG", "AGA", "AGG"],
    "G": ["GGT", "GGC", "GGA", "GGG"],
}

_AA_TO_CODON = {aa: codons[0] for aa, codons in _CODON_TABLE.items()}

_DNA_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def _protein_to_dna(aa_seq: str) -> str:
    """Back-translate an amino-acid sequence to DNA using common codons."""
    return "".join(_AA_TO_CODON.get(aa, "NNN") for aa in aa_seq)


def _translate(nt_seq: str) -> str:
    """Translate a DNA sequence to protein."""
    protein = []
    for i in range(0, len(nt_seq) - 2, 3):
        codon = nt_seq[i:i + 3]
        protein.append(_DNA_CODON_TABLE.get(codon, "X"))
    return "".join(protein)
