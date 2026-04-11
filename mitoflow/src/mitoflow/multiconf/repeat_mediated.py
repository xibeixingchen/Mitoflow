"""Multi-configuration structure analysis for plant mitochondrial genomes.

Plant mitochondrial genomes exist as a dynamic mixture of subgenomic
molecules mediated by recombination across large repeat pairs.
This module:
1. Detects large repeat pairs (direct and inverted)
2. Predicts subgenomic configurations
3. Optionally validates with long reads
"""

from __future__ import annotations
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models.genome import GenomeSequence

logger = logging.getLogger(__name__)


@dataclass
class RepeatPair:
    """A pair of large repeat sequences."""
    id: str
    repeat_type: str              # "direct" | "inverted"
    copy1_start: int              # 1-based
    copy1_end: int
    copy2_start: int
    copy2_end: int
    length: int
    identity: float
    recombination_active: Optional[bool] = None
    recombination_ratio: Optional[float] = None


@dataclass
class SubgenomicCircle:
    """A predicted subgenomic configuration."""
    id: str
    parent_repeat: str            # RepeatPair id
    configuration: str            # "master_circle" | "subcircle_1" | "subcircle_2"
    size: int                     # bp
    genes: list = field(default_factory=list)
    is_major: bool = False
    description: str = ""


@dataclass
class MulticonfResult:
    """Complete multi-configuration analysis result."""
    repeat_pairs: list = field(default_factory=list)   # RepeatPair
    subgenomic_circles: list = field(default_factory=list)  # SubgenomicCircle
    n_configurations: int = 1
    has_multi_conf: bool = False
    recombination_level: str = "stable"  # "active" | "low_freq" | "stable"
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== Multi-configuration Analysis ===",
            f"Large repeats (>=100bp, >=95%): {len(self.repeat_pairs)}",
            f"Predicted configurations: {self.n_configurations}",
            f"Recombination level: {self.recombination_level}",
        ]
        for rp in self.repeat_pairs:
            lines.append(
                f"  Repeat {rp.id}: {rp.repeat_type}, {rp.length:,} bp, "
                f"id={rp.identity:.1f}%, "
                f"pos=({rp.copy1_start:,}-{rp.copy1_end:,}) "
                f"({rp.copy2_start:,}-{rp.copy2_end:,})"
            )
        if self.subgenomic_circles:
            lines.append("")
            lines.append("Subgenomic configurations:")
            for sg in self.subgenomic_circles:
                lines.append(
                    f"  {sg.id}: {sg.configuration}, {sg.size:,} bp, "
                    f"{len(sg.genes)} genes"
                    f"{'*' if sg.is_major else ''}"
                )
        return "\n".join(lines)


def predict_subgenomes(
    genome: GenomeSequence,
    fasta_path: Path,
    gene_annotations: Optional[list] = None,
    min_repeat_length: int = 100,
    min_identity: float = 95.0,
) -> MulticonfResult:
    """Predict subgenomic configurations from repeat pairs.

    For each Direct Repeat (DR) pair: master circle splits into 2 subcircles.
    For each Inverted Repeat (IR) pair: produces 2 isomeric master circles.

    Args:
        genome: GenomeSequence object.
        fasta_path: Path to FASTA file.
        gene_annotations: Gene annotations for labeling subcircles.
        min_repeat_length: Minimum repeat length to consider.
        min_identity: Minimum identity for repeat pair.

    Returns:
        MulticonfResult with repeat pairs and predicted configurations.
    """
    result = MulticonfResult()

    # Step 1: Find large repeats
    repeat_pairs = _find_repeats(fasta_path, min_repeat_length, min_identity)
    result.repeat_pairs = repeat_pairs

    if not repeat_pairs:
        result.warnings.append("No large repeats detected — genome appears stable")
        return result

    # Step 2: Build gene position map
    gene_positions = {}
    if gene_annotations:
        for ann in gene_annotations:
            gene_positions[ann.gene_name] = (ann.genomic_start, ann.genomic_end)

    # Step 3: Predict configurations for each repeat pair
    config_id = 0
    for rp in repeat_pairs:
        if rp.repeat_type == "direct":
            # DR splits master circle into 2 subcircles
            sub1, sub2 = _predict_dr_subcircles(
                rp, len(genome.sequence), gene_positions, config_id,
            )
            result.subgenomic_circles.extend([sub1, sub2])
            config_id += 2
        elif rp.repeat_type == "inverted":
            # IR produces 2 isomeric master circles
            iso1, iso2 = _predict_ir_isomers(
                rp, len(genome.sequence), gene_positions, config_id,
            )
            result.subgenomic_circles.extend([iso1, iso2])
            config_id += 2

    # Step 4: Summary
    result.n_configurations = 1 + len(result.subgenomic_circles)
    result.has_multi_conf = len(result.subgenomic_circles) > 0

    # Determine recombination level
    active_repeats = [rp for rp in repeat_pairs if rp.recombination_active]
    if len(active_repeats) > 0:
        active_ratios = [rp.recombination_ratio for rp in active_repeats
                        if rp.recombination_ratio is not None]
        if active_ratios and max(active_ratios) > 0.1:
            result.recombination_level = "active"
        elif active_ratios and max(active_ratios) > 0.01:
            result.recombination_level = "low_freq"

    return result


def verify_recombination_with_longreads(
    fasta_path: Path,
    longreads_path: str,
    repeat_pairs: list,
    min_support: int = 3,
) -> list:
    """Verify recombination activity using long reads.

    For each repeat pair, check if long reads support both configurations:
    - Reads crossing repeat junction in orientation A → configuration 1
    - Reads crossing repeat junction in orientation B → configuration 2

    Recombination ratio = min(A, B) / (A + B)

    >10%: active recombination (multiple configurations coexist)
    1-10%: low frequency (substoichiometric shift)
    <1%: essentially stable

    Args:
        fasta_path: Genome FASTA.
        longreads_path: Long read FASTQ.
        repeat_pairs: List of RepeatPair to verify.
        min_support: Minimum reads to call recombination.

    Returns:
        Updated RepeatPair list with recombination data.
    """
    minimap2 = shutil.which("minimap2")
    samtools = shutil.which("samtools")
    if not minimap2 or not samtools:
        for rp in repeat_pairs:
            rp.recombination_active = None
        return repeat_pairs

    genome_len = 0
    with open(fasta_path) as f:
        for line in f:
            if not line.startswith(">"):
                genome_len += len(line.strip())

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Map long reads
        bam_out = tmp / "mapped.bam"
        try:
            proc = subprocess.run(
                [minimap2, "-ax", "map-pb", "-t", "4",
                 str(fasta_path), longreads_path],
                capture_output=True, timeout=600,
            )
            with open(tmp / "mapped.sam", "wb") as f:
                f.write(proc.stdout)

            subprocess.run(
                [samtools, "sort", "-o", str(bam_out), str(tmp / "mapped.sam")],
                capture_output=True, timeout=120,
            )
            subprocess.run(
                [samtools, "index", str(bam_out)],
                capture_output=True, timeout=60,
            )
        except Exception as e:
            logger.warning(f"Long read mapping failed: {e}")
            return repeat_pairs

        # For each repeat pair, count reads supporting each configuration
        for rp in repeat_pairs:
            rp.recombination_active = False
            rp.recombination_ratio = 0.0

            config_a = 0  # Configuration A reads
            config_b = 0  # Configuration B reads

            # Extract reads crossing repeat boundaries
            try:
                # Check flanking region 1
                region1 = f"{rp.copy1_start - 500}-{rp.copy1_end + 500}"
                region2 = f"{rp.copy2_start - 500}-{rp.copy2_end + 500}"

                proc = subprocess.run(
                    [samtools, "view", str(bam_out)],
                    capture_output=True, text=True, timeout=60,
                )

                for line in proc.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = line.split("\t")
                    if len(parts) < 4:
                        continue

                    try:
                        read_start = int(parts[3])
                        cigar = parts[5]
                        # Estimate read end from CIGAR
                        ref_consumed = 0
                        import re
                        for match in re.finditer(r"(\d+)([MIDNSHP=X])", cigar):
                            length = int(match.group(1))
                            op = match.group(2)
                            if op in ("M", "D", "N", "=", "X"):
                                ref_consumed += length
                        read_end = read_start + ref_consumed
                    except (ValueError, IndexError):
                        continue

                    # Check if read crosses repeat boundary
                    crosses_copy1 = (read_start < rp.copy1_end and
                                    read_end > rp.copy1_end)
                    crosses_copy2 = (read_start < rp.copy2_end and
                                    read_end > rp.copy2_end)

                    if crosses_copy1 or crosses_copy2:
                        config_a += 1

            except Exception:
                pass

            # Determine activity
            total = config_a + config_b
            if total >= min_support:
                ratio = min(config_a, config_b) / total
                rp.recombination_ratio = ratio
                rp.recombination_active = ratio > 0.01

    return repeat_pairs


# ── Internal helpers ─────────────────────────────────────────────

def _find_repeats(
    fasta_path: Path, min_length: int, min_identity: float,
) -> list:
    """Find large repeat pairs using BLAST self-comparison."""
    blastn = shutil.which("blastn")
    makeblastdb = shutil.which("makeblastdb")
    if not blastn or not makeblastdb:
        return []

    repeats = []

    with tempfile.TemporaryDirectory() as tmpdir:
        db = Path(tmpdir) / "self_db"
        subprocess.run(
            [makeblastdb, "-in", str(fasta_path), "-dbtype", "nucl",
             "-out", str(db)],
            capture_output=True, timeout=120,
        )

        proc = subprocess.run(
            [blastn, "-query", str(fasta_path), "-db", str(db),
             "-outfmt", "6 qstart qend sstart send pident length",
             "-evalue", "1e-10", "-max_target_seqs", "100",
             "-dust", "no"],
            capture_output=True, text=True, timeout=300,
        )

        if proc.returncode != 0:
            return []

        seen = set()
        repeat_id = 0

        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            try:
                qstart, qend = int(parts[0]), int(parts[1])
                sstart, send = int(parts[2]), int(parts[3])
                pident = float(parts[4])
                length = int(parts[5])
            except ValueError:
                continue

            if length < min_length or pident < min_identity:
                continue

            # Skip self-hits and overlaps
            key = (min(qstart, sstart), max(qstart, sstart))
            if abs(qstart - sstart) < min_length:
                continue
            if key in seen:
                continue
            seen.add(key)

            # Determine type
            q_len = abs(qend - qstart)
            s_len = abs(send - sstart)
            if (qend - qstart) * (send - sstart) > 0:
                rtype = "direct"
            else:
                rtype = "inverted"

            repeat_id += 1
            repeats.append(RepeatPair(
                id=f"repeat_{repeat_id:03d}",
                repeat_type=rtype,
                copy1_start=min(qstart, qend),
                copy1_end=max(qstart, qend),
                copy2_start=min(sstart, send),
                copy2_end=max(sstart, send),
                length=length,
                identity=pident,
            ))

    # Sort by length (largest first)
    repeats.sort(key=lambda r: r.length, reverse=True)
    return repeats


def _predict_dr_subcircles(
    repeat: RepeatPair, genome_length: int,
    gene_positions: dict, start_id: int,
) -> tuple:
    """Predict subgenomic circles from a direct repeat pair.

    A DR divides the master circle into two subcircles:
    - Subcircle 1: region between repeat copies (exclusive)
    - Subcircle 2: remaining region + one repeat copy at each end
    """
    # Region A: between repeat copies
    region_a_start = repeat.copy1_end + 1
    region_a_end = repeat.copy2_start - 1
    region_a_size = max(0, region_a_end - region_a_start + 1)

    # Region B: outside repeat copies
    region_b_size = genome_length - region_a_size - 2 * repeat.length

    # Subcircle 1: Region A + repeat at boundaries
    sub1_size = region_a_size + 2 * repeat.length
    sub1_genes = _genes_in_range(
        gene_positions, region_a_start, region_a_end
    )

    # Subcircle 2: Region B + repeat at boundaries
    sub2_size = region_b_size + 2 * repeat.length
    sub2_genes = _genes_outside_range(
        gene_positions, region_a_start, region_a_end, genome_length
    )

    sub1 = SubgenomicCircle(
        id=f"subcircle_{start_id + 1}",
        parent_repeat=repeat.id,
        configuration="subcircle_1",
        size=sub1_size,
        genes=sub1_genes,
        is_major=sub1_size > sub2_size,
        description=f"DR-mediated subcircle ({sub1_size:,} bp, {len(sub1_genes)} genes)",
    )

    sub2 = SubgenomicCircle(
        id=f"subcircle_{start_id + 2}",
        parent_repeat=repeat.id,
        configuration="subcircle_2",
        size=sub2_size,
        genes=sub2_genes,
        is_major=sub2_size > sub1_size,
        description=f"DR-mediated subcircle ({sub2_size:,} bp, {len(sub2_genes)} genes)",
    )

    return sub1, sub2


def _predict_ir_isomers(
    repeat: RepeatPair, genome_length: int,
    gene_positions: dict, start_id: int,
) -> tuple:
    """Predict isomeric configurations from an inverted repeat pair.

    An IR produces two isomeric master circles:
    - Isomer 1: original orientation
    - Isomer 2: region between IRs inverted
    """
    region_start = repeat.copy1_end + 1
    region_end = repeat.copy2_start - 1

    inverted_genes = _genes_in_range(gene_positions, region_start, region_end)

    iso1 = SubgenomicCircle(
        id=f"isomer_{start_id + 1}",
        parent_repeat=repeat.id,
        configuration="isomer_1",
        size=genome_length,
        genes=list(gene_positions.keys()),
        is_major=True,
        description="IR-isomer: original orientation",
    )

    iso2 = SubgenomicCircle(
        id=f"isomer_{start_id + 2}",
        parent_repeat=repeat.id,
        configuration="isomer_2",
        size=genome_length,
        genes=list(gene_positions.keys()),
        is_major=False,
        description=f"IR-isomer: inverted region ({region_start:,}-{region_end:,})",
    )

    return iso1, iso2


def _genes_in_range(gene_positions: dict, start: int, end: int) -> list:
    """Get gene names within a genomic range."""
    genes = []
    for name, (gs, ge) in gene_positions.items():
        if gs >= start and ge <= end:
            genes.append(name)
    return genes


def _genes_outside_range(
    gene_positions: dict, start: int, end: int, genome_length: int,
) -> list:
    """Get gene names outside a genomic range."""
    genes = []
    for name, (gs, ge) in gene_positions.items():
        if not (gs >= start and ge <= end):
            genes.append(name)
    return genes
