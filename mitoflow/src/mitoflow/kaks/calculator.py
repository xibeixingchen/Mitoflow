"""Ka/Ks (dN/dS) selection pressure analysis for plant mitochondrial genes.

Uses KaKs_Calculator-3.0 (C++ external tool) with multiple methods:
MA (Model Average), NG, LWL, LPB, GY, YN, ALL.

Plant mitochondria considerations:
  - Use standard genetic code (NCBI Table 1), NOT Table 2.
  - Ks is typically very low due to slow point mutation rate.
  - When Ks ≈ 0, Ka/Ks is undefined and marked "NA".
  - RNA-editing-corrected sequences should be used when available.

Reference:
  Zhang Z (2022) KaKs_Calculator 3.0. Genomics Proteomics Bioinformatics 20(3):536-540.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standard genetic code (NCBI Table 1) — used by plant mitochondria
# ---------------------------------------------------------------------------
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

# Functional categories for grouped visualization
GENE_CATEGORIES = {
    "Complex I": [
        "nad1", "nad2", "nad3", "nad4", "nad4L",
        "nad5", "nad6", "nad7", "nad9",
    ],
    "Complex III": ["cob"],
    "Complex IV": ["cox1", "cox2", "cox3"],
    "Complex V": ["atp1", "atp4", "atp6", "atp8", "atp9"],
    "CCM": ["ccmB", "ccmC", "ccmFC", "ccmFN"],
    "Ribosomal": [
        "rpl2", "rpl5", "rpl10", "rpl16",
        "rps1", "rps2", "rps3", "rps4", "rps7",
        "rps10", "rps12", "rps13", "rps14", "rps19",
    ],
    "Other": ["matR", "mttB", "sdh3", "sdh4"],
}


def _gene_category(name: str) -> str:
    """Return the functional category for a gene name."""
    low = name.lower()
    for cat, genes in GENE_CATEGORIES.items():
        if low in (g.lower() for g in genes):
            return cat
    return "Other"


# ===================================================================
# Data classes
# ===================================================================

@dataclass
class KaKsResult:
    """Ka/Ks result for a single gene pair."""

    gene: str = ""
    species_a: str = "A"
    species_b: str = "B"

    ka: float = 0.0
    ks: float = 0.0
    kaks_ratio: float = 0.0

    alignment_codons: int = 0   # number of valid codon pairs compared
    identity_pct: float = 0.0

    selection: str = "NA"       # purifying | neutral | positive | NA
    method: str = "KaKs_Calculator-MA"
    category: str = ""

    def classify_selection(self, threshold_purifying: float = 1.0) -> str:
        """Classify selection type from Ka/Ks ratio.

        Standard thresholds:
          Ka/Ks < 1   → purifying selection (most mito genes)
          Ka/Ks ≈ 1   → neutral evolution
          Ka/Ks > 1   → positive selection (rare in mito)
          Ks ≈ 0      → undefined
        """
        if self.ks < 1e-6:
            return "NA"
        if self.kaks_ratio < threshold_purifying:
            return "purifying"
        elif self.kaks_ratio <= 1.5:
            return "neutral"
        else:
            return "positive"


@dataclass
class KaKsBatchResult:
    """Collection of Ka/Ks results across multiple genes / species."""

    results: list[KaKsResult] = field(default_factory=list)
    per_gene: dict[str, list[KaKsResult]] = field(default_factory=dict)
    per_species_pair: dict[str, list[KaKsResult]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a human-readable summary string."""
        lines = [
            "=== Ka/Ks Analysis Summary ===",
            f"Total gene pairs analysed: {len(self.results)}",
        ]
        valid = [r for r in self.results if r.selection != "NA"]
        na_count = len(self.results) - len(valid)
        if valid:
            ratios = [r.kaks_ratio for r in valid]
            mean_r = sum(ratios) / len(ratios)
            median_r = sorted(ratios)[len(ratios) // 2]
            purifying = sum(1 for r in valid if r.selection == "purifying")
            neutral = sum(1 for r in valid if r.selection == "neutral")
            positive = sum(1 for r in valid if r.selection == "positive")
            lines += [
                f"  Valid pairs: {len(valid)}",
                f"  Mean Ka/Ks:   {mean_r:.4f}",
                f"  Median Ka/Ks: {median_r:.4f}",
                f"  Purifying: {purifying}  Neutral: {neutral}  Positive: {positive}",
            ]
        if na_count:
            lines.append(f"  Undetermined (Ks≈0): {na_count}")
        return "\n".join(lines)


# ===================================================================
# Pairwise alignment (used for CDS alignment before AXT generation)
# ===================================================================

def _align_cds_pair(seq_a: str, seq_b: str) -> tuple[str, str]:
    """Align two CDS sequences using MAFFT (protein-guided).

    Strategy:
      1. Translate both CDS to protein.
      2. Align proteins with MAFFT.
      3. Back-translate to codon-aware nucleotide alignment.

    Falls back to direct comparison if MAFFT is not installed or fails.

    Returns:
        Tuple of aligned nucleotide sequences (with gaps as '---').
    """
    mafft = shutil.which("mafft")
    if not mafft:
        logger.debug("MAFFT not found; using unaligned sequences")
        return seq_a, seq_b

    # Translate to protein for alignment
    prot_a = _translate(seq_a)
    prot_b = _translate(seq_b)
    if not prot_a or not prot_b:
        return seq_a, seq_b

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        fa_in = tmp / "prot.fasta"
        fa_in.write_text(f">A\n{prot_a}\n>B\n{prot_b}\n")

        try:
            proc = subprocess.run(
                [mafft, "--auto", "--quiet", str(fa_in)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                return seq_a, seq_b

            # Parse aligned proteins
            aligned = _parse_fasta_string(proc.stdout)
            if len(aligned) != 2:
                return seq_a, seq_b

            aln_prot_a = aligned[0]
            aln_prot_b = aligned[1]

            # Back-translate: each amino acid → original codon, gap → "---"
            nt_a = _back_translate(aln_prot_a, seq_a)
            nt_b = _back_translate(aln_prot_b, seq_b)
            return nt_a, nt_b

        except (subprocess.TimeoutExpired, Exception) as e:
            logger.debug(f"MAFFT alignment failed: {e}")
            return seq_a, seq_b


def _translate(nt_seq: str) -> str:
    """Translate a nucleotide sequence to protein (Table 1, no stop)."""
    aa = []
    for i in range(0, len(nt_seq) - 2, 3):
        codon = nt_seq[i:i + 3]
        residue = CODON_TABLE.get(codon, "X")
        if residue == "*":
            break
        aa.append(residue)
    return "".join(aa)


def _back_translate(aligned_prot: str, original_nt: str) -> str:
    """Convert an aligned protein sequence back to codon-level nucleotides.

    Gaps in the protein alignment become '---' in the nucleotide output.
    """
    nt_parts = []
    codon_idx = 0
    for aa in aligned_prot:
        if aa == "-":
            nt_parts.append("---")
        else:
            start = codon_idx * 3
            end = start + 3
            if end <= len(original_nt):
                nt_parts.append(original_nt[start:end])
            else:
                nt_parts.append("NNN")
            codon_idx += 1
    return "".join(nt_parts)


def _parse_fasta_string(text: str) -> list[str]:
    """Parse a FASTA-formatted string and return list of sequences."""
    seqs = []
    current = []
    for line in text.strip().split("\n"):
        if line.startswith(">"):
            if current:
                seqs.append("".join(current))
                current = []
        else:
            current.append(line.strip())
    if current:
        seqs.append("".join(current))
    return seqs


# ===================================================================
# Output
# ===================================================================

def write_kaks_tables(
    results: list[KaKsBatchResult],
    output_dir: Path,
    prefix: str = "mitoflow",
) -> dict[str, Path]:
    """Write Ka/Ks results to TSV files.

    Produces:
      - {prefix}_kaks.tsv: full results table
      - {prefix}_kaks_summary.txt: text summary

    Returns:
        Dict of output file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}

    # --- Full TSV ---
    tsv_path = output_dir / f"{prefix}_kaks.tsv"
    with open(tsv_path, "w") as fh:
        header = (
            "gene\tcategory\tspecies_a\tspecies_b\t"
            "Ka\tKs\tKa_Ks\t"
            "codons\tidentity_pct\tmethod\tselection\n"
        )
        fh.write(header)
        for batch in results:
            for r in batch.results:
                ratio_str = f"{r.kaks_ratio:.4f}" if r.selection != "NA" else "NA"
                fh.write(
                    f"{r.gene}\t{r.category}\t{r.species_a}\t{r.species_b}\t"
                    f"{r.ka:.6f}\t{r.ks:.6f}\t{ratio_str}\t"
                    f"{r.alignment_codons}\t{r.identity_pct:.1f}\t"
                    f"{r.method}\t{r.selection}\n"
                )
    files["kaks_tsv"] = tsv_path
    logger.info(f"Ka/Ks table written to {tsv_path}")

    # --- Summary ---
    summary_path = output_dir / f"{prefix}_kaks_summary.txt"
    with open(summary_path, "w") as fh:
        for batch in results:
            fh.write(batch.summary())
            fh.write("\n\n")
    files["kaks_summary"] = summary_path

    return files


# ===================================================================
# KaKs_Calculator-3.0 integration
# ===================================================================

def check_kaks_calculator_available() -> bool:
    """Check if KaKs_Calculator-3.0 binary is available in PATH."""
    return shutil.which("KaKs") is not None


def _generate_axt_file(
    gene_name: str,
    aligned_seq_a: str,
    aligned_seq_b: str,
    species_a: str,
    species_b: str,
) -> str:
    """Generate AXT format string for one gene pair.

    AXT format:
        header line: seq_name_a seq_name_b
        aligned sequence a
        aligned sequence b
        (empty line)
    """
    return f"{species_a}_{gene_name} {species_b}_{gene_name}\n{aligned_seq_a}\n{aligned_seq_b}\n\n"


def _write_axt_file(axt_entries: list[str], output_path: Path) -> Path:
    """Write multiple AXT entries to a single file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for entry in axt_entries:
            f.write(entry)
    return output_path


def _run_kaks_calculator(
    axt_path: Path,
    output_path: Path,
    method: str = "MA",
    genetic_code: int = 1,
) -> Path:
    """Run KaKs_Calculator-3.0 on an AXT file.

    Args:
        axt_path: Input AXT file.
        output_path: Output results file.
        method: Calculation method (MA, NG, LWL, LPB, GY, YN, ALL, etc.).
        genetic_code: NCBI genetic code table (1=Standard for plant mito).

    Returns:
        Path to the output file.

    Raises:
        RuntimeError: If KaKs binary is not found or execution fails.
    """
    kaks_bin = shutil.which("KaKs")
    if not kaks_bin:
        raise RuntimeError("KaKs_Calculator-3.0 binary not found in PATH")

    cmd = [
        kaks_bin,
        "-i", str(axt_path),
        "-o", str(output_path),
        "-m", method,
        "-c", str(genetic_code),
    ]
    logger.info("Running KaKs_Calculator: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"KaKs_Calculator failed: {result.stderr}")
    if not output_path.exists():
        raise RuntimeError(f"KaKs_Calculator produced no output: {output_path}")
    return output_path


def _parse_kaks_calculator_output(output_path: Path) -> list[dict]:
    """Parse KaKs_Calculator-3.0 output file.

    Returns list of dicts with keys: gene_pair, Ka, Ks, Ka/Ks, method, etc.
    """
    results = []
    with open(output_path) as f:
        header = f.readline().strip().split("\t")
        for line in f:
            fields = line.strip().split("\t")
            if len(fields) < len(header):
                continue
            row = dict(zip(header, fields))
            results.append(row)
    return results


def _extract_cds_from_record(record) -> dict[str, str]:
    """Extract CDS sequences from a BioPython SeqRecord."""
    cds = {}
    for feat in record.features:
        if feat.type != "CDS":
            continue
        name = feat.qualifiers.get("gene", feat.qualifiers.get("locus_tag", [""]))[0]
        if not name:
            continue
        try:
            seq = str(feat.extract(record.seq)).upper()
            if len(seq) >= 3:
                cds[name] = seq
        except Exception:
            continue
    return cds


def _clean_alignment(seq_a: str, seq_b: str) -> tuple[str, str]:
    """Remove gap columns and ensure length is a multiple of 3.

    Mimics pal2nal -nogap -nomismatch behavior.
    """
    clean_a, clean_b = [], []
    for a, b in zip(seq_a, seq_b):
        if a == "-" or b == "-":
            continue
        if a == "N" or b == "N":
            continue
        clean_a.append(a)
        clean_b.append(b)
    # Truncate to multiple of 3
    aligned_a = "".join(clean_a)
    aligned_b = "".join(clean_b)
    trim = len(aligned_a) - (len(aligned_a) % 3)
    return aligned_a[:trim], aligned_b[:trim]


def _extract_gene_from_pair(gene_pair: str) -> str:
    """Extract gene name from KaKs_Calculator output 'Sequence' field.

    Format: "query_genename ref_genename" or "speciesA_genename speciesB_genename".
    """
    parts = gene_pair.split()
    if not parts:
        return ""
    # Take first part and extract gene name after species prefix
    name = parts[0]
    # Remove common prefixes: "query_", "queryName_"
    if "_" in name:
        # Skip the first segment (species prefix), take the rest as gene name
        segments = name.split("_", 1)
        if len(segments) >= 2:
            return segments[1]
    return name


def batch_kaks(
    query_gbk: Path,
    reference_gbks: list[Path],
    query_name: str = "query",
    reference_names: Optional[list[str]] = None,
    output_dir: Optional[Path] = None,
    method: str = "MA",
    genetic_code: int = 1,
    min_identity: float = 30.0,
) -> list[KaKsBatchResult]:
    """Calculate Ka/Ks using KaKs_Calculator-3.0.

    Supports multiple methods (MA, NG, LWL, LPB, GY, YN, ALL).
    Requires KaKs_Calculator-3.0 to be installed and in PATH.

    Args:
        query_gbk: Query GenBank file.
        reference_gbks: List of reference GenBank files.
        query_name: Display name for query.
        reference_names: Display names for references.
        output_dir: If provided, write intermediate and result files.
        method: KaKs calculation method (default: MA = Model Average).
        genetic_code: NCBI genetic code (1=Standard for plant mitochondria).
        min_identity: Minimum identity (%) to keep a result.

    Returns:
        List of KaKsBatchResult.

    Raises:
        RuntimeError: If KaKs_Calculator-3.0 is not available.
    """
    if not check_kaks_calculator_available():
        raise RuntimeError(
            "KaKs_Calculator-3.0 not found in PATH. "
            "Install from: https://github.com/Chenglin20170390/KaKs_Calculator-3.0"
        )

    from Bio import SeqIO

    all_results = []

    for i, ref_gbk in enumerate(reference_gbks):
        ref_name = (
            reference_names[i]
            if reference_names and i < len(reference_names)
            else Path(ref_gbk).stem
        )
        logger.info(f"KaKs_Calculator: comparing {query_name} vs {ref_name}")

        # Parse both GenBank files
        query_record = SeqIO.read(str(query_gbk), "genbank")
        ref_record = SeqIO.read(str(ref_gbk), "genbank")

        # Extract CDS sequences and align
        query_cds = _extract_cds_from_record(query_record)
        ref_cds = _extract_cds_from_record(ref_record)

        shared_genes = set(query_cds.keys()) & set(ref_cds.keys())
        if not shared_genes:
            batch = KaKsBatchResult(
                results=[],
                per_gene={},
                per_species_pair={f"{query_name}_vs_{ref_name}": []},
                warnings=[f"No shared genes between {query_name} and {ref_name}"],
            )
            all_results.append(batch)
            continue

        # Generate AXT entries for shared genes
        axt_entries = []
        gene_alignments = {}
        for gene in sorted(shared_genes):
            seq_a = query_cds[gene]
            seq_b = ref_cds[gene]
            aligned_a, aligned_b = _align_cds_pair(seq_a, seq_b)
            # Remove gaps and mismatches for AXT (pal2nal-style)
            aligned_a, aligned_b = _clean_alignment(aligned_a, aligned_b)
            if len(aligned_a) < 3 or len(aligned_a) % 3 != 0:
                continue
            axt_entries.append(
                _generate_axt_file(gene, aligned_a, aligned_b, query_name, ref_name)
            )
            gene_alignments[gene] = (aligned_a, aligned_b)

        if not axt_entries:
            batch = KaKsBatchResult(
                results=[], per_gene={}, per_species_pair={},
                warnings=["No valid alignments after cleaning"],
            )
            all_results.append(batch)
            continue

        # Write AXT file and run KaKs_Calculator
        with tempfile.TemporaryDirectory(prefix="mitoflow_kaks_") as tmpdir:
            axt_path = Path(tmpdir) / "input.axt"
            kaks_out = Path(tmpdir) / "output.kaks"
            _write_axt_file(axt_entries, axt_path)

            _run_kaks_calculator(axt_path, kaks_out, method=method, genetic_code=genetic_code)

            # Parse results
            parsed = _parse_kaks_calculator_output(kaks_out)
            kaks_results = []
            per_gene: dict[str, list[KaKsResult]] = {}

            for row in parsed:
                gene_pair = row.get("Sequence", "")
                # Parse gene name from pair like "query_nad1_ref_nad1"
                gene_name = _extract_gene_from_pair(gene_pair)
                if not gene_name:
                    continue

                try:
                    ka = float(row.get("Ka", "NA").replace("NA", "0"))
                    ks = float(row.get("Ks", "NA").replace("NA", "0"))
                    kaks_ratio = float(row.get("Ka/Ks", "NA").replace("NA", "0"))
                except (ValueError, TypeError):
                    continue

                # Filter by identity
                identity = 0.0
                if gene_name in gene_alignments:
                    a, b = gene_alignments[gene_name]
                    matches = sum(1 for x, y in zip(a, b) if x == y and x != "-")
                    total = sum(1 for x, y in zip(a, b) if x != "-" and y != "-")
                    identity = matches / total * 100 if total > 0 else 0
                if identity < min_identity:
                    continue

                # Classify selection
                if ks <= 0.001:
                    selection = "NA"
                elif kaks_ratio < 1:
                    selection = "purifying"
                elif kaks_ratio < 1.5:
                    selection = "neutral"
                else:
                    selection = "positive"

                category = _gene_category(gene_name)
                r = KaKsResult(
                    gene=gene_name,
                    species_a=query_name,
                    species_b=ref_name,
                    ka=ka, ks=ks, kaks_ratio=kaks_ratio,
                    alignment_codons=len(gene_alignments.get(gene_name, ("", ""))[0]) // 3,
                    identity_pct=identity,
                    selection=selection,
                    method=f"KaKs_Calculator-{method}",
                    category=category,
                )
                kaks_results.append(r)
                per_gene.setdefault(gene_name, []).append(r)

            batch = KaKsBatchResult(
                results=kaks_results,
                per_gene=per_gene,
                per_species_pair={f"{query_name}_vs_{ref_name}": kaks_results},
                warnings=[],
            )
            all_results.append(batch)
            logger.info(batch.summary())

    if output_dir:
        write_kaks_tables(all_results, Path(output_dir))

    return all_results
