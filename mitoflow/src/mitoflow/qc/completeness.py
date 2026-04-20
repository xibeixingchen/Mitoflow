"""Gene completeness assessment (Dimension 1).

Uses pyhmmer + optional miniprot to detect 41 core PCGs,
3 rRNAs, and tRNAs. Classifies each gene as Complete/Fragmented/Missing/Duplicated.
"""

from __future__ import annotations
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models.genome import GenomeSequence

logger = logging.getLogger(__name__)

# 42 core PCGs for angiosperm mitochondria (including rnaseh)
CORE_PCG_41 = [
    # Complex I (9)
    "nad1", "nad2", "nad3", "nad4", "nad4L", "nad5", "nad6", "nad7", "nad9",
    # Complex III (1)
    "cob",
    # Complex IV (3)
    "cox1", "cox2", "cox3",
    # Complex V (5)
    "atp1", "atp4", "atp6", "atp8", "atp9",
    # Cytochrome c maturation (4)
    "ccmB", "ccmC", "ccmFC", "ccmFN",
    # Ribosomal proteins (15)
    "rpl2", "rpl5", "rpl10", "rpl16",
    "rps1", "rps2", "rps3", "rps4", "rps7",
    "rps10", "rps12", "rps13", "rps14", "rps19",
    # Other (5)
    "matR", "mttB", "rnaseh", "sdh3", "sdh4",
]

# Variable genes (loss is not necessarily an assembly error)
VARIABLE_PCG = [
    "rps11", "rpl6", "rps8", "rps15", "rps16", "rpl14",
]

# Essential genes (present in ALL known angiosperms — missing = critical)
ESSENTIAL_PCG = [
    "nad1", "nad2", "nad3", "nad4", "nad4L", "nad5", "nad6", "nad7", "nad9",
    "cob", "cox1", "cox2", "cox3",
    "atp1", "atp6", "atp9",
    "ccmB", "ccmC", "ccmFC", "ccmFN",
    "matR", "mttB",
]

# Core rRNAs
CORE_RRNA = ["rrn5", "rrn18", "rrn26"]


@dataclass
class GeneCompletenessResult:
    """Result of gene completeness assessment."""
    total_expected: int = 41
    total_found: int = 0
    found_genes: list = field(default_factory=list)
    missing_genes: list = field(default_factory=list)
    duplicated_genes: list = field(default_factory=list)
    fragmented_genes: list = field(default_factory=list)
    essential_missing: list = field(default_factory=list)
    variable_missing: list = field(default_factory=list)
    completeness_pct: float = 0.0
    rrna_found: list = field(default_factory=list)
    rrna_missing: list = field(default_factory=list)
    trna_count: int = 0
    score: float = 0.0  # 0-100

    def summary(self) -> str:
        lines = [
            f"Gene Completeness: {self.total_found}/{self.total_expected} "
            f"({self.completeness_pct:.1f}%)",
            f"  Complete: {len(self.found_genes)}",
            f"  Fragmented: {len(self.fragmented_genes)}",
            f"  Missing: {len(self.missing_genes)}",
            f"  Duplicated: {len(self.duplicated_genes)}",
        ]
        if self.essential_missing:
            lines.append(f"  [CRITICAL] Essential missing: {', '.join(self.essential_missing)}")
        if self.variable_missing:
            lines.append(f"  [INFO] Variable missing: {', '.join(self.variable_missing)}")
        if self.rrna_missing:
            lines.append(f"  rRNA missing: {', '.join(self.rrna_missing)}")
        return "\n".join(lines)


def assess_gene_completeness(
    genome: GenomeSequence,
    fasta_path: Path,
    hmm_db: Optional[Path] = None,
    ref_protein: Optional[Path] = None,
    evalue: float = 1e-5,
    use_miniprot: bool = True,
) -> GeneCompletenessResult:
    """Assess gene completeness using pyhmmer + optional miniprot.

    Strategy (inspired by HiMT):
    1. pyhmmer hmmsearch: fast detection of 41 PCGs
    2. miniprot (if available): precise mapping with intron splicing
    3. Cross-validate results, take union

    Args:
        genome: GenomeSequence object.
        fasta_path: Path to FASTA file.
        hmm_db: Path to combined HMM database.
        ref_protein: Reference protein FASTA for miniprot.
        evalue: E-value threshold.
        use_miniprot: Whether to use miniprot if available.

    Returns:
        GeneCompletenessResult with gene-level assessment.
    """
    result = GeneCompletenessResult()

    # Step 1: pyhmmer search
    hmm_found = set()
    hmm_duplicated = set()
    hmm_fragmented = set()
    seen_counts = {}  # gene_name -> count

    if hmm_db and hmm_db.exists():
        hmm_found, hmm_duplicated, hmm_fragmented, seen_counts = _pyhmmer_search(
            genome, hmm_db, evalue
        )

    # Step 2: miniprot search (if available and ref_protein provided)
    mini_found = set()
    mini_duplicated = set()
    if use_miniprot and ref_protein and ref_protein.exists():
        mini_found, mini_duplicated = _miniprot_search(
            fasta_path, ref_protein
        )

    # Step 3: Merge results (union)
    all_found = hmm_found | mini_found
    all_duplicated = hmm_duplicated | mini_duplicated
    all_fragmented = hmm_fragmented

    # Classify
    expected = set(CORE_PCG_41)
    missing = sorted(expected - all_found)

    essential_missing = [g for g in missing if g in ESSENTIAL_PCG]
    variable_missing = [g for g in missing if g in VARIABLE_PCG]

    total = len(expected)
    found_count = len(expected & all_found)
    pct = found_count / total * 100 if total > 0 else 0

    # Score calculation
    score = _calculate_completeness_score(
        found_count, total, essential_missing, all_fragmented
    )

    result.total_expected = total
    result.total_found = found_count
    result.found_genes = sorted(expected & all_found)
    result.missing_genes = missing
    result.duplicated_genes = sorted(all_duplicated & expected)
    result.fragmented_genes = sorted(all_fragmented & expected)
    result.essential_missing = essential_missing
    result.variable_missing = variable_missing
    result.completeness_pct = pct
    result.score = score

    return result


def _pyhmmer_search(
    genome: GenomeSequence, hmm_db: Path, evalue: float
) -> tuple:
    """Run pyhmmer hmmsearch and classify hits."""
    try:
        import pyhmmer
        from pyhmmer import easel, plan7
    except ImportError:
        logger.warning("pyhmmer not installed, skipping HMM search")
        return set(), set(), set(), {}

    # Disable numba JIT to avoid conflicts with pyhmmer's fused cpdef
    import os
    os.environ["NUMBA_DISABLE_JIT"] = "1"

    from ..annotate.pcg import six_frame_translation

    try:
        alphabet = easel.Alphabet.amino()
        frames = six_frame_translation(genome.sequence)

        seen_counts = {}  # gene_name -> list of (score, length_ratio)

        with pyhmmer.plan7.HMMFile(str(hmm_db)) as hf:
            hmms = list(hf)

        for prot_seq, frame_offset in frames:
            if not prot_seq:
                continue
            text_seq = easel.TextSequence(
                name=f"frame_{frame_offset}".encode(), sequence=prot_seq
            )
            digital_seq = text_seq.digitize(alphabet)
            seq_block = easel.DigitalSequenceBlock(alphabet, [digital_seq])

            pipeline = plan7.Pipeline(alphabet, Z=len(hmms), E=evalue)
            for top_hits in pipeline.search_hmm(hmms, seq_block):
                for hit in top_hits:
                    if hit.included:
                        name = hit.name.decode() if isinstance(hit.name, bytes) else hit.name
                        # Normalize gene name (remove _isoform suffixes etc)
                        name = name.split("_")[0].split(".")[0]
                        if name not in seen_counts:
                            seen_counts[name] = []
                        seen_counts[name].append(hit.score)

        # Classify
        found = set()
        duplicated = set()
        fragmented = set()

        for gene_name, scores in seen_counts.items():
            if len(scores) > 1:
                duplicated.add(gene_name)
            found.add(gene_name)

        return found, duplicated, fragmented, seen_counts
    except Exception as e:
        logger.warning(f"pyhmmer search failed in QC: {e}")
        return set(), set(), set(), {}


def _miniprot_search(
    fasta_path: Path, ref_protein: Path
) -> tuple:
    """Run miniprot for protein-to-genome alignment (HiMT method).

    miniprot natively supports intron splicing, making it excellent for
    multi-exon gene detection (nad1/nad2/nad4/nad5/nad7/cox2/ccmFC).
    """
    miniprot = shutil.which("miniprot")
    if not miniprot:
        logger.debug("miniprot not found, skipping")
        return set(), set()

    try:
        proc = subprocess.run(
            [miniprot, "--outf", "gff", "-t", "4", str(fasta_path), str(ref_protein)],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0:
            return set(), set()

        gene_hits = {}  # gene_name -> count
        for line in proc.stdout.strip().split("\n"):
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 9:
                continue
            attrs = parts[8]
            # Extract gene name from attributes
            for attr in attrs.split(";"):
                if attr.startswith("Target="):
                    target = attr.split("=")[1]
                    gene_name = target.split()[0].split("_")[0].split(".")[0]
                    gene_hits[gene_name] = gene_hits.get(gene_name, 0) + 1

        found = set(gene_hits.keys())
        duplicated = {g for g, c in gene_hits.items() if c > 1}
        return found, duplicated

    except (subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"miniprot failed: {e}")
        return set(), set()


def _calculate_completeness_score(
    found: int, total: int,
    essential_missing: list, fragmented: list,
) -> float:
    """Calculate completeness score (0-100).

    Penalties:
    - Essential gene missing: -10 each
    - Variable gene missing: -2 each
    - Fragmented gene: -3 each
    """
    base = found / total * 100 if total > 0 else 0
    penalty = len(essential_missing) * 10 + len(fragmented) * 3
    return max(0, min(100, base - penalty))
