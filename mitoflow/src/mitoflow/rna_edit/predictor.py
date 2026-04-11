"""RNA editing prediction for plant mitochondrial genomes.

Predicts C-to-U RNA editing sites using comparative genomics:
1. Translate CDS from genomic DNA (uncorrected)
2. BLAST against reference edited proteins
3. Pairwise alignment to detect C→U corrections
4. Classify: synonymous, start-gain (ACG→AUG), stop-removal

Plant mitochondria typically have 300-600 C-to-U editing sites.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# NCBI Table 1 codons
CODON_TABLE = {
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

# Known stop-gain genes (C→U creates stop)
STOP_GAIN_GENES = {"ccmFC", "rps10", "atp9", "atp6", "rps11"}

# Known start-gain genes (ACG→AUG via editing)
START_GAIN_GENES = {"cox1", "nad1", "nad4L", "rps10"}

# Amino acid change patterns from C→U editing
# C→U at codon positions: any C in codon → U
# Common changes: Ser→Leu, Pro→Leu, Ser→Phe, Pro→Ser, Thr→Ile, Ala→Val


@dataclass
class EditingSite:
    """A predicted RNA editing site."""
    gene: str
    position_cds: int              # 1-based position in CDS
    position_genome: int           # 1-based genome coordinate
    codon_position: int            # 1, 2, or 3
    original_codon: str
    edited_codon: str
    original_aa: str
    edited_aa: str
    is_synonymous: bool
    is_start_codon_creation: bool  # ACG→AUG
    is_stop_codon_removal: bool    # internal CAA/CAG/CGA → UAA/UAG/UGA
    confidence: str = "medium"     # "high" | "medium" | "low"


@dataclass
class EditingResult:
    """Complete RNA editing prediction result."""
    sites: list = field(default_factory=list)
    total_sites: int = 0
    nonsynonymous: int = 0
    synonymous: int = 0
    start_codon_creations: int = 0
    stop_codon_removals: int = 0
    codon_pos1: int = 0
    codon_pos2: int = 0
    codon_pos3: int = 0
    aa_changes: dict = field(default_factory=dict)  # (from_aa, to_aa) -> count
    per_gene_counts: dict = field(default_factory=dict)  # gene -> count
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== RNA Editing Prediction ===",
            f"Total predicted sites: {self.total_sites}",
            f"  Nonsynonymous: {self.nonsynonymous} ({self.nonsynonymous / max(self.total_sites, 1) * 100:.1f}%)",
            f"  Synonymous:    {self.synonymous} ({self.synonymous / max(self.total_sites, 1) * 100:.1f}%)",
            f"  Codon position 1: {self.codon_pos1} ({self.codon_pos1 / max(self.total_sites, 1) * 100:.1f}%)",
            f"  Codon position 2: {self.codon_pos2} ({self.codon_pos2 / max(self.total_sites, 1) * 100:.1f}%)",
            f"  Codon position 3: {self.codon_pos3} ({self.codon_pos3 / max(self.total_sites, 1) * 100:.1f}%)",
            f"  Start codon creations: {self.start_codon_creations}",
            f"  Stop codon removals:   {self.stop_codon_removals}",
        ]
        if self.aa_changes:
            lines.append("")
            lines.append("  Amino acid changes (Top 10):")
            sorted_changes = sorted(self.aa_changes.items(), key=lambda x: -x[1])[:10]
            for (from_aa, to_aa), count in sorted_changes:
                pct = count / max(self.nonsynonymous, 1) * 100
                lines.append(f"    {from_aa} -> {to_aa}: {count} ({pct:.1f}%)")
        return "\n".join(lines)


def predict_editing_by_homology(
    genome_seq: str,
    gene_name: str,
    cds_seq: str,
    cds_start: int,
    strand: int,
    reference_protein: str,
    min_identity: float = 50.0,
) -> list:
    """Predict editing sites for a single gene by comparing genomic
    translation against reference (edited) protein.

    Algorithm:
    1. Translate genomic CDS (uncorrected)
    2. Align with reference protein
    3. For each mismatch: check if C→U in CDS could fix it
    4. Validate: edited codon must match reference amino acid

    Args:
        genome_seq: Full genome sequence.
        gene_name: Gene name.
        cds_seq: CDS nucleotide sequence (already oriented).
        cds_start: 1-based start of first exon in genome.
        strand: +1 or -1.
        reference_protein: Reference edited protein sequence.
        min_identity: Minimum alignment identity.

    Returns:
        List of EditingSite predictions.
    """
    sites = []

    # Translate genomic CDS
    genomic_protein = _translate(cds_seq)
    if not genomic_protein:
        return sites

    # Simple pairwise alignment
    ref_prot = reference_protein.upper().rstrip("*")
    gen_prot = genomic_protein.rstrip("*")

    if not ref_prot or not gen_prot:
        return sites

    # Align using simple Needleman-Wunsch or just iterate
    matches = 0
    alignment_len = min(len(ref_prot), len(gen_prot))

    if alignment_len == 0:
        return sites

    for i in range(alignment_len):
        if gen_prot[i] == ref_prot[i]:
            matches += 1

    identity = matches / alignment_len * 100
    if identity < min_identity:
        return sites

    # Check each amino acid mismatch
    for i in range(alignment_len):
        gen_aa = gen_prot[i]
        ref_aa = ref_prot[i]

        if gen_aa == ref_aa:
            continue

        # Check if C→U editing could explain the difference
        codon_idx = i * 3
        if codon_idx + 2 >= len(cds_seq):
            continue

        codon = cds_seq[codon_idx:codon_idx + 3].upper()
        if len(codon) < 3:
            continue

        # Try C→U at each position in the codon
        for pos in range(3):
            if codon[pos] != "C":
                continue

            edited = list(codon)
            edited[pos] = "T"  # C→U = T in DNA
            edited_codon = "".join(edited)

            edited_aa = CODON_TABLE.get(edited_codon, "X")
            if edited_aa == ref_aa:
                # Found a valid editing site
                is_syn = (gen_aa == edited_aa)
                is_start = (i == 0 and codon == "ACG" and edited_codon == "ATG")

                original_stop = CODON_TABLE.get(codon, "") == "*"
                edited_not_stop = edited_aa != "*"
                is_stop_removal = (not original_stop and not edited_not_stop)

                # Calculate genome position
                genome_pos = _cds_to_genome_pos(
                    codon_idx + pos + 1, cds_start, strand, len(genome_seq)
                )

                site = EditingSite(
                    gene=gene_name,
                    position_cds=codon_idx + pos + 1,
                    position_genome=genome_pos,
                    codon_position=pos + 1,
                    original_codon=codon,
                    edited_codon=edited_codon,
                    original_aa=gen_aa,
                    edited_aa=edited_aa,
                    is_synonymous=is_syn,
                    is_start_codon_creation=is_start,
                    is_stop_codon_removal=is_stop_removal,
                    confidence="high" if identity > 80 else "medium",
                )
                sites.append(site)
                break  # Only one C per codon position needed

    return sites


def predict_editing_from_known_sites(
    gene_name: str,
    cds_seq: str,
    cds_start: int,
    strand: int,
    genome_length: int,
) -> list:
    """Predict editing based on known rules (no external reference needed).

    Applies known patterns:
    - Stop-gain genes: CAA→UAA, CAG→UAG, CGA→UGA (internal stops)
    - Start-gain genes: ACG→AUG at position 1
    """
    sites = []

    # Start codon check (ACG→AUG)
    if gene_name.lower() in {g.lower() for g in START_GAIN_GENES}:
        start_codon = cds_seq[:3].upper()
        if start_codon == "ACG":
            genome_pos = _cds_to_genome_pos(1, cds_start, strand, genome_length)
            sites.append(EditingSite(
                gene=gene_name,
                position_cds=1,
                position_genome=genome_pos,
                codon_position=1,
                original_codon="ACG",
                edited_codon="ATG",
                original_aa="T",
                edited_aa="M",
                is_synonymous=False,
                is_start_codon_creation=True,
                is_stop_codon_removal=False,
                confidence="high",
            ))

    # Internal stop codon check
    if gene_name.lower() in {g.lower() for g in STOP_GAIN_GENES}:
        genomic_protein = _translate(cds_seq)
        if genomic_protein:
            for i, aa in enumerate(genomic_protein):
                if aa == "*" and i < len(genomic_protein) - 1:
                    # Not the real stop — check if C→U editing could remove it
                    codon_idx = i * 3
                    if codon_idx + 2 >= len(cds_seq):
                        continue
                    codon = cds_seq[codon_idx:codon_idx + 3].upper()
                    if len(codon) < 3:
                        continue

                    for pos in range(3):
                        if codon[pos] != "C":
                            continue
                        edited = list(codon)
                        edited[pos] = "T"
                        edited_codon = "".join(edited)
                        edited_aa = CODON_TABLE.get(edited_codon, "X")

                        if edited_aa != "*":
                            genome_pos = _cds_to_genome_pos(
                                codon_idx + pos + 1, cds_start, strand, genome_length
                            )
                            sites.append(EditingSite(
                                gene=gene_name,
                                position_cds=codon_idx + pos + 1,
                                position_genome=genome_pos,
                                codon_position=pos + 1,
                                original_codon=codon,
                                edited_codon=edited_codon,
                                original_aa="*",
                                edited_aa=edited_aa,
                                is_synonymous=False,
                                is_start_codon_creation=False,
                                is_stop_codon_removal=True,
                                confidence="high",
                            ))
                            break

    return sites


def correct_protein_with_editing(
    cds_seq: str,
    sites: list,
) -> str:
    """Apply predicted editing sites to CDS and translate corrected protein.

    Args:
        cds_seq: Original CDS sequence.
        sites: List of EditingSite for this gene.

    Returns:
        Corrected protein sequence.
    """
    corrected = list(cds_seq.upper())
    for site in sites:
        pos = site.position_cds - 1  # 0-based
        if pos < len(corrected) and corrected[pos] == "C":
            corrected[pos] = "T"  # C→U

    corrected_seq = "".join(corrected)
    return _translate(corrected_seq)


def build_editing_result(sites: list) -> EditingResult:
    """Build EditingResult statistics from a list of EditingSites."""
    result = EditingResult(sites=sites)
    result.total_sites = len(sites)

    for site in sites:
        if site.is_synonymous:
            result.synonymous += 1
        else:
            result.nonsynonymous += 1
            key = (site.original_aa, site.edited_aa)
            result.aa_changes[key] = result.aa_changes.get(key, 0) + 1

        if site.codon_position == 1:
            result.codon_pos1 += 1
        elif site.codon_position == 2:
            result.codon_pos2 += 1
        else:
            result.codon_pos3 += 1

        if site.is_start_codon_creation:
            result.start_codon_creations += 1
        if site.is_stop_codon_removal:
            result.stop_codon_removals += 1

        result.per_gene_counts[site.gene] = result.per_gene_counts.get(site.gene, 0) + 1

    return result


# ── Internal helpers ─────────────────────────────────────────────

def _translate(seq: str) -> str:
    """Translate nucleotide sequence using NCBI Table 1."""
    protein = []
    seq = seq.upper()
    for i in range(0, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        if len(codon) < 3:
            break
        aa = CODON_TABLE.get(codon, "X")
        protein.append(aa)
        if aa == "*":
            break
    return "".join(protein)


def _cds_to_genome_pos(
    cds_pos: int, cds_start: int, strand: int, genome_length: int
) -> int:
    """Convert CDS position (1-based) to genome position (1-based)."""
    if strand == 1:
        return cds_start + cds_pos - 1
    else:
        return cds_start - cds_pos + 1
