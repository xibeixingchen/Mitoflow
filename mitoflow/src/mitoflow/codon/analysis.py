"""Codon usage analysis for plant mitochondrial genomes.

Calculates:
1. RSCU (Relative Synonymous Codon Usage)
2. ENC (Effective Number of Codons)
3. ENC-plot (ENC vs GC3s)
4. Third position base bias
5. Amino acid frequency
6. Start codon statistics

Plant mitochondria use NCBI Table 1 (standard genetic code).
"""

from __future__ import annotations
import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# NCBI Table 1 — standard genetic code
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

# Amino acids and their synonymous codons
AA_TO_CODONS = defaultdict(list)
for codon, aa in CODON_TABLE.items():
    if aa != "*":
        AA_TO_CODONS[aa].append(codon)

# 59 sense codons (excluding Met=ATG, Trp=TGG which have no synonyms)
SENSE_CODONS = [c for c, aa in CODON_TABLE.items() if aa != "*"]


@dataclass
class CodonUsageResult:
    """Complete codon usage analysis result."""
    # Overall
    overall_rscu: dict = field(default_factory=dict)   # codon -> RSCU
    overall_codon_count: dict = field(default_factory=dict)
    overall_aa_freq: dict = field(default_factory=dict)
    start_codons: dict = field(default_factory=dict)

    # Per-gene
    per_gene_rscu: dict = field(default_factory=dict)   # gene -> {codon: RSCU}
    per_gene_enc: dict = field(default_factory=dict)     # gene -> ENC
    per_gene_gc3s: dict = field(default_factory=dict)    # gene -> GC3s
    per_gene_gc12: dict = field(default_factory=dict)    # gene -> GC12 (positions 1+2)
    per_gene_pr2: dict = field(default_factory=dict)     # gene -> {A3, T3, G3, C3} counts

    # Summary
    n_genes: int = 0
    total_codons: int = 0
    mean_enc: float = 0.0
    mean_gc3s: float = 0.0

    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== Codon Usage Analysis ===",
            f"Genes analyzed: {self.n_genes}",
            f"Total codons: {self.total_codons:,}",
            f"Mean ENC: {self.mean_enc:.1f} (range: {min(self.per_gene_enc.values()):.1f}"
            f"- {max(self.per_gene_enc.values()):.1f})" if self.per_gene_enc else "",
            f"Mean GC3s: {self.mean_gc3s:.3f}",
            "",
            "Start codons:",
        ]
        for codon, count in sorted(self.start_codons.items(), key=lambda x: -x[1]):
            pct = count / sum(self.start_codons.values()) * 100
            lines.append(f"  {codon}: {count} ({pct:.1f}%)")
        return "\n".join(lines)


def analyze_codon_usage(
    genbank_path: Path,
    min_cds_length: int = 100,
) -> CodonUsageResult:
    """Run complete codon usage analysis from GenBank file.

    Args:
        genbank_path: Input GenBank file.
        min_cds_length: Minimum CDS length to include.

    Returns:
        CodonUsageResult with all statistics.
    """
    from Bio import SeqIO

    result = CodonUsageResult()

    record = next(SeqIO.parse(str(genbank_path), "genbank"))
    genome_seq = str(record.seq).upper()

    overall_codons = Counter()
    overall_aa = Counter()
    start_codons = Counter()

    gene_codons = {}  # gene -> Counter
    gene_seqs = {}    # gene -> cds_seq

    for feat in record.features:
        if feat.type != "CDS":
            continue

        gene_name = ""
        if "gene" in feat.qualifiers:
            gene_name = feat.qualifiers["gene"][0]
        elif "locus_tag" in feat.qualifiers:
            gene_name = feat.qualifiers["locus_tag"][0]
        if not gene_name:
            continue

        # Extract CDS sequence
        try:
            cds_seq = str(feat.extract(record.seq)).upper()
        except Exception:
            continue

        if len(cds_seq) < min_cds_length:
            continue

        # Remove trailing stop codon if present
        if len(cds_seq) % 3 == 0:
            last_codon = cds_seq[-3:]
            if CODON_TABLE.get(last_codon) == "*":
                cds_seq = cds_seq[:-3]

        if len(cds_seq) < 3 or len(cds_seq) % 3 != 0:
            continue

        # Count codons
        codons = _count_codons(cds_seq)
        gene_codons[gene_name] = codons
        gene_seqs[gene_name] = cds_seq

        overall_codons.update(codons)
        for codon, count in codons.items():
            aa = CODON_TABLE.get(codon)
            if aa and aa != "*":
                overall_aa[aa] += count

        # Start codon
        start = cds_seq[:3]
        start_codons[start] += 1

    if not gene_codons:
        result.warnings.append("No valid CDS found for codon analysis")
        return result

    # Overall RSCU
    result.overall_codon_count = dict(overall_codons)
    result.overall_aa_freq = dict(overall_aa)
    result.overall_rscu = _calculate_rscu(overall_codons)
    result.start_codons = dict(start_codons)

    # Per-gene analysis
    enc_values = []
    gc3s_values = []

    for gene_name, codons in gene_codons.items():
        result.per_gene_rscu[gene_name] = _calculate_rscu(codons)
        enc = _calculate_enc(codons)
        result.per_gene_enc[gene_name] = enc
        enc_values.append(enc)

        cds_seq = gene_seqs[gene_name]
        gc3s = _calculate_gc3s(cds_seq)
        result.per_gene_gc3s[gene_name] = gc3s
        gc3s_values.append(gc3s)

        gc12 = _calculate_gc12(cds_seq)
        result.per_gene_gc12[gene_name] = gc12

        pr2 = _calculate_pr2(cds_seq)
        result.per_gene_pr2[gene_name] = pr2

    result.n_genes = len(gene_codons)
    result.total_codons = sum(overall_codons.values())
    result.mean_enc = sum(enc_values) / len(enc_values) if enc_values else 0
    result.mean_gc3s = sum(gc3s_values) / len(gc3s_values) if gc3s_values else 0

    return result


def _count_codons(seq: str) -> Counter:
    """Count all codons in a sequence."""
    codons = Counter()
    for i in range(0, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        if len(codon) == 3 and "N" not in codon:
            codons[codon] += 1
    return codons


def _calculate_rscu(codon_counts: Counter) -> dict:
    """Calculate RSCU (Relative Synonymous Codon Usage).

    RSCU_ij = X_ij / (n_i / j_count)
    where X_ij = observed count of codon j for amino acid i
    n_i = total observed count of all synonymous codons for aa i

    RSCU = 1.0 = no bias
    RSCU > 1.0 = preferred codon
    RSCU < 1.0 = avoided codon
    """
    rscu = {}

    # Group codons by amino acid
    aa_codons = defaultdict(list)
    for codon, count in codon_counts.items():
        aa = CODON_TABLE.get(codon)
        if aa and aa != "*":
            aa_codons[aa].append((codon, count))

    for aa, codon_list in aa_codons.items():
        if len(codon_list) < 2:
            # No synonymous codons (Met, Trp)
            for codon, count in codon_list:
                rscu[codon] = 1.0
            continue

        total = sum(count for _, count in codon_list)
        n_synonymous = len(codon_list)

        for codon, count in codon_list:
            expected = total / n_synonymous
            rscu[codon] = count / expected if expected > 0 else 0.0

    return rscu


def _calculate_enc(codon_counts: Counter) -> float:
    """Calculate ENC (Effective Number of Codons) — Wright 1990.

    ENC ranges from 20 (one codon per aa) to 61 (all codons equally used).
    Formula: F = (n * F_avg - 1) / (n - 1)
    ENC = 2 + 9/F2 + 1/F3 + 5/F4 + 3/F6
    where Fk is the average homozygosity for amino acids with k synonymous codons.
    """
    # Group by amino acid
    aa_codons = defaultdict(list)
    for codon, count in codon_counts.items():
        aa = CODON_TABLE.get(codon)
        if aa and aa != "*":
            aa_codons[aa].append(count)

    # Calculate F for each amino acid family
    f_values = {2: [], 3: [], 4: [], 6: []}

    for aa, counts in aa_codons.items():
        n_synonyms = len(counts)
        total = sum(counts)

        if total == 0:
            continue

        # Calculate F for this amino acid
        p_values = [c / total for c in counts]
        f_aa = sum(p * p for p in p_values)

        # Also need the correction: F = (n * sum(pi^2) - 1) / (n - 1)
        # where n = total codon count for this aa
        if total > 1:
            f_corrected = (total * f_aa - 1) / (total - 1)
        else:
            f_corrected = 1.0

        # Classify by degeneracy
        if n_synonyms in f_values:
            f_values[n_synonyms].append(f_corrected)

    # Calculate average F for each degeneracy class
    enc = 2.0  # Start with 2 (for Met and Trp which have no synonyms)

    for degeneracy, f_list in f_values.items():
        if f_list:
            f_avg = sum(f_list) / len(f_list)
            multiplier = {2: 9, 3: 1, 4: 5, 6: 3}[degeneracy]
            if f_avg > 0:
                enc += multiplier / f_avg
        # If no data for this class, add max contribution (F=1, no bias)
        else:
            enc += {2: 9, 3: 1, 4: 5, 6: 3}[degeneracy]

    return min(61.0, max(20.0, enc))


def _calculate_gc3s(seq: str) -> float:
    """Calculate GC content at third codon position (GC3s).

    Excludes Met (ATG), Trp (TGG), and stop codons.
    """
    gc3 = 0
    total = 0

    for i in range(0, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        if len(codon) < 3:
            break
        aa = CODON_TABLE.get(codon)
        if not aa or aa == "*":
            continue

        third = codon[2].upper()
        if third in ("G", "C", "A", "T"):
            total += 1
            if third in ("G", "C"):
                gc3 += 1

    return gc3 / total if total > 0 else 0.0


def _calculate_gc12(seq: str) -> float:
    """Calculate GC content at first and second codon positions (GC12).

    Excludes stop codons.
    """
    gc = 0
    total = 0

    for i in range(0, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        if len(codon) < 3:
            break
        aa = CODON_TABLE.get(codon)
        if not aa or aa == "*":
            continue
        for pos in (0, 1):
            total += 1
            if codon[pos] in ("G", "C"):
                gc += 1

    return gc / total if total > 0 else 0.0


def _calculate_pr2(seq: str) -> dict:
    """Calculate PR2 bias (Parity Rule 2) at third codon position.

    Returns dict with A3, T3, G3, C3 counts at third position,
    excluding Met, Trp, and stop codons.
    """
    counts = {"A": 0, "T": 0, "G": 0, "C": 0}

    for i in range(0, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        if len(codon) < 3:
            break
        aa = CODON_TABLE.get(codon)
        if not aa or aa == "*":
            continue
        # Skip Met (ATG) and Trp (TGG) — no synonymous codons
        if codon in ("ATG", "TGG"):
            continue
        third = codon[2].upper()
        if third in counts:
            counts[third] += 1

    return counts


def calculate_enc_expected(gc3s: float) -> float:
    """Calculate expected ENC for a given GC3s value.

    Formula: Nc_expected = 2 + GC3s + 29 / (GC3s^2 + (1-GC3s)^2)
    Wright 1990, used for ENC-plot.
    """
    if gc3s <= 0 or gc3s >= 1:
        return 61.0
    return 2 + gc3s + 29 / (gc3s ** 2 + (1 - gc3s) ** 2)


def write_codon_tables(
    result: CodonUsageResult,
    output_dir: Path,
    name: str = "MitoFlow",
) -> dict:
    """Write codon usage analysis results to files.

    Returns dict of file paths written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    # RSCU table
    rscu_path = output_dir / f"{name}_rscu.tsv"
    with open(rscu_path, "w") as f:
        f.write("gene\t" + "\t".join(sorted(SENSE_CODONS)) + "\n")
        for gene in sorted(result.per_gene_rscu.keys()):
            rscu = result.per_gene_rscu[gene]
            values = [f"{rscu.get(c, 0):.3f}" for c in sorted(SENSE_CODONS)]
            f.write(gene + "\t" + "\t".join(values) + "\n")
        # Overall
        values = [f"{result.overall_rscu.get(c, 0):.3f}" for c in sorted(SENSE_CODONS)]
        f.write("OVERALL\t" + "\t".join(values) + "\n")
    files["rscu_tsv"] = rscu_path

    # ENC-GC3s-GC12 table
    enc_path = output_dir / f"{name}_enc.tsv"
    with open(enc_path, "w") as f:
        f.write("gene\tENC\tGC3s\tGC12")
        # PR2 bias ratios
        f.write("\tA3/(A3+T3)\tG3/(G3+C3)\n")
        for gene in sorted(result.per_gene_enc.keys()):
            gc12 = result.per_gene_gc12.get(gene, 0)
            pr2 = result.per_gene_pr2.get(gene, {})
            a3 = pr2.get("A", 0)
            t3 = pr2.get("T", 0)
            g3 = pr2.get("G", 0)
            c3 = pr2.get("C", 0)
            at_bias = a3 / (a3 + t3) if (a3 + t3) > 0 else 0
            gc_bias = g3 / (g3 + c3) if (g3 + c3) > 0 else 0
            f.write(f"{gene}\t{result.per_gene_enc[gene]:.2f}\t"
                    f"{result.per_gene_gc3s[gene]:.4f}\t{gc12:.4f}\t"
                    f"{at_bias:.4f}\t{gc_bias:.4f}\n")
    files["enc_tsv"] = enc_path

    # Amino acid frequency
    aa_path = output_dir / f"{name}_aa_freq.tsv"
    with open(aa_path, "w") as f:
        f.write("amino_acid\tcount\tfrequency\n")
        total_aa = sum(result.overall_aa_freq.values())
        for aa in sorted(result.overall_aa_freq.keys()):
            count = result.overall_aa_freq[aa]
            freq = count / total_aa if total_aa > 0 else 0
            f.write(f"{aa}\t{count}\t{freq:.4f}\n")
    files["aa_freq_tsv"] = aa_path

    logger.info(f"Codon usage tables written to {output_dir}")
    return files
