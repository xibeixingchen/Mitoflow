"""Trans-spliced gene handling for plant mitochondria.

Trans-spliced genes have exons scattered across genome:
- nad1/nad2/nad5: 5 exons each
- nad4/nad7: 4 exons each
- cox2/rpl2/rps3/ccmFC: 2 exons

Some exons are very short (<30bp), missed by HMM search.
This module provides utilities to detect and validate trans-spliced gene structure.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from Bio.Seq import Seq

from ..models.genome import GenomeSequence
from ..models.gene import GeneAnnotation, ExonRecord, Strand
from ..db.manager import DBManager

logger = logging.getLogger(__name__)

# Known trans-spliced genes and their expected exon counts
# Based on plant mitochondrial gene structure literature
TRANS_SPLICING_INFO = {
    "nad1": {"exons": 5, "min_exon_bp": 15, "note": "5 trans-spliced exons"},
    "nad2": {"exons": 5, "min_exon_bp": 15, "note": "5 trans-spliced exons"},
    "nad5": {"exons": 5, "min_exon_bp": 20, "note": "5 trans-spliced exons, exon3 is often 22bp"},
    "nad4": {"exons": 4, "min_exon_bp": 30, "note": "4 cis-spliced exons"},
    "nad7": {"exons": 5, "min_exon_bp": 30, "note": "5 cis-spliced exons"},
    # Multi-exon genes with cis-splicing (exons close together)
    "cox2": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons"},
    "rpl2": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons"},
    "rps3": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons"},
    "ccmFC": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons"},
    "rps10": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons (exon1 ~250bp, exon2 ~83bp)"},
}


def validate_trans_spliced_genes(
    annotations: list[GeneAnnotation],
    db_manager: DBManager,
) -> list[str]:
    """Validate trans-spliced genes have expected exon counts.

    Args:
        annotations: List of gene annotations
        db_manager: Database manager

    Returns:
        List of warnings for genes with fewer exons than expected
    """
    warnings = []

    for ann in annotations:
        gene_name = ann.gene_name
        if gene_name not in TRANS_SPLICING_INFO:
            continue

        expected = TRANS_SPLICING_INFO[gene_name]["exons"]
        actual = len(ann.exons)

        if actual < expected:
            warning = (
                f"{gene_name}: found {actual} exons, expected {expected}. "
                f"Missing short exons may be undetected (<30bp)."
            )
            warnings.append(warning)
            logger.warning(warning)

    return warnings


def detect_short_exons(
    genome: GenomeSequence,
    db_manager: DBManager,
    found_genes: dict[str, GeneAnnotation],
) -> dict[str, GeneAnnotation]:
    """Detect short exons for trans-spliced genes using BLASTn.

    For genes like nad5 where some exons are <30bp and missed by HMM,
    use BLASTn-short against reference exon sequences.

    Args:
        genome: Genome sequence
        db_manager: Database manager
        found_genes: Already annotated genes (from HMM search)

    Returns:
        Updated gene annotations with short exons added (if found)
    """
    blastn = shutil.which("blastn")
    if not blastn:
        logger.warning("blastn not available, skipping short exon detection")
        return found_genes

    updated = {}
    ref_dir = db_manager.exon_ref_dir

    for gene_name, info in TRANS_SPLICING_INFO.items():
        if gene_name not in found_genes:
            continue

        ann = found_genes[gene_name]

        # Check if we have fewer exons than expected
        if len(ann.exons) >= info["exons"]:
            continue

        logger.info(
            f"{gene_name}: found {len(ann.exons)} exons, expected {info['exons']}. "
            f"Searching for missing short exons."
        )

        # Look for exon reference files
        exon_ref = _find_exon_reference(gene_name, ref_dir)
        if not exon_ref:
            logger.debug(f"No exon reference file for {gene_name}, skipping")
            continue

        # Search for short exons using BLASTn-short
        missing_exons = _search_short_exons_blast(
            gene_name, genome, exon_ref, ann.exons, info["min_exon_bp"], blastn
        )

        if missing_exons:
            # Add missing exons
            all_exons = list(ann.exons) + missing_exons
            all_exons.sort(key=lambda e: e.start)

            # Re-number exons
            numbered = [
                ExonRecord(start=e.start, end=e.end, strand=e.strand, number=i)
                for i, e in enumerate(all_exons, 1)
            ]

            updated[gene_name] = ann.model_copy(update={"exons": numbered})
            logger.info(
                f"{gene_name}: added {len(missing_exons)} short exons, "
                f"now {len(numbered)} total"
            )

    # Merge updates
    for name, ann in updated.items():
        found_genes[name] = ann

    return found_genes


def _circular_gene_span(exons: list[ExonRecord], genome_length: int) -> int:
    """Compute the minimal arc length on a circular genome that contains all exons.

    Strategy: the largest gap between consecutive exons (including wrap-around)
    is the portion of the genome that does NOT need to be covered. The span is
    genome_length minus that largest gap.
    """
    if not exons:
        return 0
    if len(exons) == 1:
        return exons[0].end - exons[0].start + 1

    sorted_exons = sorted(exons, key=lambda e: e.start)
    max_gap = 0
    for i in range(len(sorted_exons) - 1):
        gap = sorted_exons[i + 1].start - sorted_exons[i].end - 1
        if gap > max_gap:
            max_gap = gap
    # Wrap-around gap
    wrap_gap = sorted_exons[0].start + (genome_length - sorted_exons[-1].end) - 1
    if wrap_gap > max_gap:
        max_gap = wrap_gap

    span = genome_length - max_gap
    return span


def _find_exon_reference(gene_name: str, ref_dir: Path) -> Path | None:
    """Find exon reference file for a gene.

    Looks for nucleotide reference files:
    1. {gene_name}_exons.fasta (individual exon sequences)
    2. {gene_name}.CDS.fasta (full CDS sequence)
    3. {gene_name}.CDS.Exons.Extent.fasta (multi-species exon fragments)

    Note: Protein.fasta files are NOT suitable for blastn (requires nucleotide).
    """
    # Check for exon-specific reference
    exon_ref = ref_dir / f"{gene_name}_exons.fasta"
    if exon_ref.exists():
        return exon_ref

    # Check for CDS reference
    cds_ref = ref_dir / f"{gene_name}.CDS.fasta"
    if cds_ref.exists():
        return cds_ref

    # Phase 3: support multi-species exon fragment files
    extent_ref = ref_dir / f"{gene_name}.CDS.Exons.Extent.fasta"
    if extent_ref.exists():
        return extent_ref

    # Check if only Protein.fasta exists (not usable for blastn)
    protein_ref = ref_dir / f"{gene_name}.Protein.fasta"
    if protein_ref.exists():
        logger.warning(
            f"Only Protein.fasta found for {gene_name}, but blastn requires "
            f"nucleotide reference (*_exons.fasta or *.CDS.fasta). "
            f"Skipping short exon detection."
        )

    return None


def _search_short_exons_blast(
    gene_name: str,
    genome: GenomeSequence,
    exon_ref: Path,
    existing_exons: list[ExonRecord],
    min_exon_bp: int,
    blastn: str,
) -> list[ExonRecord]:
    """BLASTn-short search for short exons not found by HMM.

    Uses blastn-short task which is optimized for sequences <50bp.

    Args:
        gene_name: Gene name
        genome: Genome sequence
        exon_ref: Reference exon/CDS file
        existing_exons: Exons already found
        min_exon_bp: Minimum exon length to search for
        blastn: blastn executable path

    Returns:
        List of newly found short exons
    """
    found_exons = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create subject file from genome
        subject = Path(tmpdir) / "genome.fasta"
        subject.write_text(f">{genome.seqid}\n{genome.sequence}\n")

        # Make BLAST database
        makeblastdb = shutil.which("makeblastdb")
        if makeblastdb:
            try:
                subprocess.run(
                    [makeblastdb, "-in", str(subject), "-dbtype", "nucl"],
                    capture_output=True,
                    timeout=60,
                )
            except subprocess.SubprocessError:
                logger.warning("makeblastdb failed, skipping short exon search")
                return []

        out_file = Path(tmpdir) / "blast.tsv"
        cmd = [
            blastn,
            "-task", "blastn-short",  # Optimized for short sequences
            "-query", str(exon_ref),
            "-subject", str(subject),
            "-out", str(out_file),
            "-outfmt", "6 qseqid sseqid sstart send evalue bitscore length pident",
            "-evalue", "1e-5",
            "-max_target_seqs", "10",
            "-perc_identity", "80",
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
        except subprocess.SubprocessError as e:
            logger.warning(f"blastn-short failed: {e}")
            return []

        if not out_file.exists() or not out_file.read_text().strip():
            return []

        # Parse BLAST results
        for line in out_file.read_text().strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 8:
                continue

            try:
                sstart = int(parts[2])
                send = int(parts[3])
                length = int(parts[6])
                pident = float(parts[7])
            except ValueError:
                continue

            # Filter for short hits (<50bp) that could be missing exons
            # and have good identity
            if length > 50 or length < min_exon_bp:
                continue

            if pident < 80:
                continue

            # Determine strand
            if sstart <= send:
                strand = Strand.PLUS
                start, end = sstart, send
            else:
                strand = Strand.MINUS
                start, end = send, sstart

            # Check overlap with existing exons
            # Allow small overlap tolerance (10bp) for splice junctions
            overlaps = False
            for ex in existing_exons:
                overlap_len = min(end, ex.end) - max(start, ex.start) + 1
                if overlap_len > 10:
                    overlaps = True
                    break

            if not overlaps:
                found_exons.append(ExonRecord(
                    start=start, end=end, strand=strand, number=0,
                ))
                logger.debug(
                    f"{gene_name}: found potential short exon at {start}-{end} "
                    f"({length}bp, {pident:.1f}% identity)"
                )

    return found_exons


def get_expected_exon_count(gene_name: str) -> int | None:
    """Get expected exon count for a trans-spliced gene.

    Args:
        gene_name: Gene name

    Returns:
        Expected exon count, or None if gene is not known to be multi-exon
    """
    if gene_name in TRANS_SPLICING_INFO:
        return TRANS_SPLICING_INFO[gene_name]["exons"]
    return None


def is_trans_spliced_gene(gene_name: str) -> bool:
    """Check if a gene is known to be trans-spliced.

    Args:
        gene_name: Gene name

    Returns:
        True if gene has trans-spliced exons (scattered across genome)
    """
    # True trans-spliced genes: exons are far apart (>10kb)
    TRANS_SPLICED_ONLY = {"nad1", "nad2", "nad5"}
    return gene_name in TRANS_SPLICED_ONLY


# =============================================================================
# Exon Merging Logic for Trans-spliced Genes (PMGA-style)
# =============================================================================

# Configuration for trans-spliced genes: expected exons, base max_span, min exon length
# Note: max_span is dynamically adjusted based on genome length
# max_exon_gap: maximum gap between consecutive exons (None = no limit for truly trans-spliced)
TRANS_SPLICED_CONFIG_BASE = {
    "nad1": {"exons": 5, "max_span_factor": 0.7, "max_span_cap": 3000000, "min_exon_bp": 15, "max_exon_gap": None},
    "nad2": {"exons": 5, "max_span_factor": 0.6, "max_span_cap": 1500000, "min_exon_bp": 15, "max_exon_gap": None},
    "nad5": {"exons": 5, "max_span_factor": 0.7, "max_span_cap": 3000000, "min_exon_bp": 15, "max_exon_gap": None},
    "nad4": {"exons": 4, "max_span_factor": 0.3, "max_span_cap": 1500000, "min_exon_bp": 25, "max_exon_gap": None},
    "nad7": {"exons": 5, "max_span_factor": 0.3, "max_span_cap": 1500000, "min_exon_bp": 25, "max_exon_gap": None},
    "cox2": {"exons": 2, "max_span_factor": 0.1, "max_span_cap": 500000, "min_exon_bp": 50, "max_exon_gap": 10000},
    "rpl2": {"exons": 2, "max_span_factor": 0.1, "max_span_cap": 500000, "min_exon_bp": 50, "max_exon_gap": 10000},
    "rps3": {"exons": 2, "max_span_factor": 0.15, "max_span_cap": 750000, "min_exon_bp": 50, "max_exon_gap": 50000},
    "rps10": {"exons": 2, "max_span_factor": 0.01, "max_span_cap": 100000, "min_exon_bp": 50, "max_exon_gap": 5000},
}

# Default config (for backwards compatibility)
TRANS_SPLICED_CONFIG = {
    "nad1": {"exons": 5, "max_span": 1500000, "min_exon_bp": 15, "max_exon_gap": None},
    "nad2": {"exons": 5, "max_span": 500000, "min_exon_bp": 15, "max_exon_gap": None},
    "nad5": {"exons": 5, "max_span": 2000000, "min_exon_bp": 20, "max_exon_gap": None},
    "nad4": {"exons": 4, "max_span": 500000, "min_exon_bp": 30, "max_exon_gap": None},
    "nad7": {"exons": 5, "max_span": 500000, "min_exon_bp": 30, "max_exon_gap": None},
    "cox2": {"exons": 2, "max_span": 200000, "min_exon_bp": 50, "max_exon_gap": 10000},
    "rpl2": {"exons": 2, "max_span": 200000, "min_exon_bp": 50, "max_exon_gap": 10000},
    "rps3": {"exons": 2, "max_span": 500000, "min_exon_bp": 50, "max_exon_gap": 50000},
    "ccmFC": {"exons": 2, "max_span": 50000, "min_exon_bp": 50, "max_exon_gap": 10000},
    "rps10": {"exons": 2, "max_span": 50000, "min_exon_bp": 50, "max_exon_gap": 5000},
}


def get_dynamic_trans_spliced_config(genome_length: int) -> dict:
    """Calculate dynamic max_span based on genome length.

    For large genomes (>1Mbp), trans-spliced gene spans need to be scaled up
    to properly detect exons that may span across the entire genome.

    Args:
        genome_length: Total genome length in bp

    Returns:
        Updated TRANS_SPLICED_CONFIG with dynamic max_span values
    """
    dynamic_config = {}

    for gene, config in TRANS_SPLICED_CONFIG_BASE.items():
        # Calculate dynamic max_span
        max_span = min(
            genome_length * config["max_span_factor"],
            config["max_span_cap"]
        )
        # Ensure minimum span for small genomes
        max_span = max(max_span, 100000)  # Minimum 100kb

        dynamic_config[gene] = {
            "exons": config["exons"],
            "max_span": int(max_span),
            "min_exon_bp": config["min_exon_bp"],
            "max_exon_gap": config["max_exon_gap"],
        }

    logger.debug(f"Dynamic trans-spliced config for {genome_length}bp genome: nad1.max_span={dynamic_config['nad1']['max_span']}")
    return dynamic_config


def parse_exon_id(exon_id: str) -> tuple[str, int, int] | None:
    """Parse exon ID to extract gene name, exon number, and length.

    Expected ID pattern: {prefix}_{gene}_{exon_num}_{length}
    Example: "ArthCpNC-037304_cds181_nad5_1_230" -> ("nad5", 1, 230)

    Args:
        exon_id: FASTA header/ID from exon reference file

    Returns:
        Tuple of (gene_name, exon_number, exon_length) or None if parsing fails
    """
    # Pattern: look for {gene}_{num}_{length} at end of ID
    # Examples:
    #   ArthCpNC-037304_cds181_nad5_1_230 -> nad5, 1, 230
    #   refCp_cds46_rps12_2_232 -> rps12, 2, 232
    parts = exon_id.split("_")
    if len(parts) < 3:
        return None

    # Try to find pattern: gene_num_length at the end
    try:
        length = int(parts[-1])
        exon_num = int(parts[-2])
        gene_name = parts[-3]
        return (gene_name, exon_num, length)
    except (ValueError, IndexError):
        return None


def find_exon_reference_file(gene_name: str, db_manager: DBManager) -> Path | None:
    """Find exon reference file for a gene.

    Looks for files in blast_refs/exons/{gene}.CDS.Exons.Extent.fasta
    These files contain individual exon sequences for trans-spliced genes.

    Args:
        gene_name: Gene name (e.g., "nad5", "nad1")
        db_manager: Database manager with data directory

    Returns:
        Path to exon reference file or None if not found
    """
    # Primary: look for exon-specific reference in blast_refs/exons/
    exon_ref = db_manager.exon_ref_dir / f"{gene_name}.CDS.Exons.Extent.fasta"
    if exon_ref.exists():
        return exon_ref

    # Phase 3: also check for full CDS reference in blast_refs/exons/
    # (useful for genes like rps10/rpl2/ccmFC where only CDS is available)
    cds_ref = db_manager.exon_ref_dir / f"{gene_name}.CDS.fasta"
    if cds_ref.exists():
        return cds_ref

    # Legacy fallback: check for .CDS.fasta in blast_refs/pcg/
    cds_ref = db_manager.blast_ref_dir / f"{gene_name}.CDS.fasta"
    if cds_ref.exists():
        return cds_ref

    return None


def search_exons_blastn(
    gene_name: str,
    genome: GenomeSequence,
    exon_ref_file: Path,
    blastn_path: str,
) -> dict[int, list[tuple[int, int, Strand, float, int, int]]]:
    """BLASTn search for exons using exon-separated reference.

    Uses blastn with parameters optimized for exon detection:
    - -evalue 1e-10 (stringent e-value)
    - -word_size 7 (sensitive for short sequences)
    - -outfmt 6 (tabular output)

    Args:
        gene_name: Gene name for logging
        genome: Genome sequence to search
        exon_ref_file: Reference file with exon sequences
        blastn_path: Path to blastn executable

    Returns:
        Dict mapping exon_number -> list of (start, end, strand, identity, hit_length, expected_length) hits
    """
    result: dict[int, list[tuple[int, int, Strand, float, int, int]]] = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create query file from genome
        query_file = Path(tmpdir) / "genome.fasta"
        query_file.write_text(f">{genome.seqid}\n{genome.sequence}\n")

        # Create BLAST database from genome
        makeblastdb = shutil.which("makeblastdb")
        if not makeblastdb:
            logger.warning("makeblastdb not found, skipping exon search")
            return result

        try:
            subprocess.run(
                [makeblastdb, "-in", str(query_file), "-dbtype", "nucl"],
                capture_output=True,
                timeout=60,
                check=True,
            )
        except subprocess.SubprocessError as e:
            logger.warning(f"makeblastdb failed for {gene_name}: {e}")
            return result

        # Run BLASTn search
        out_file = Path(tmpdir) / "blast.tsv"
        cmd = [
            blastn_path,
            "-query", str(exon_ref_file),
            "-subject", str(query_file),
            "-out", str(out_file),
            "-outfmt", "6 qseqid sseqid sstart send evalue bitscore length pident",
            "-evalue", "1e-10",
            "-word_size", "7",
            "-max_target_seqs", "10",
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=120, check=True)
        except subprocess.SubprocessError as e:
            logger.warning(f"BLASTn search failed for {gene_name}: {e}")
            return result

        if not out_file.exists() or not out_file.read_text().strip():
            return result

        # Parse BLAST results
        for line in out_file.read_text().strip().split("\n"):
            if not line.strip():
                continue

            parts = line.split("\t")
            if len(parts) < 8:
                continue

            try:
                qseqid = parts[0]
                sstart = int(parts[2])
                send = int(parts[3])
                hit_length = int(parts[6])  # Actual hit length
                pident = float(parts[7])
            except (ValueError, IndexError):
                continue

            # Parse exon ID to get exon number and expected length
            parsed = parse_exon_id(qseqid)
            if not parsed:
                continue

            gene, exon_num, expected_length = parsed

            # Only include hits for the queried gene
            if gene != gene_name:
                continue

            # Determine strand and coordinates
            if sstart <= send:
                strand = Strand.PLUS
                start, end = sstart, send
            else:
                strand = Strand.MINUS
                start, end = send, sstart

            # Store hit with length info: (start, end, strand, identity, hit_length, expected_length)
            if exon_num not in result:
                result[exon_num] = []
            result[exon_num].append((start, end, strand, pident, hit_length, expected_length))

    return result


def _score_splice_sites(
    genome: GenomeSequence,
    start: int,
    end: int,
    strand: Strand,
) -> float:
    """Score splice-site consensus for a candidate exon hit.

    Checks the 2 bp immediately upstream of the exon start (donor)
    and downstream of the exon end (acceptor). For minus-strand genes,
    the reverse complement of the genome sequence is evaluated.

    Returns:
        Score adjustment: GT/AG +10, GC/AG +5, non-consensus -20.
    """
    score = 0.0

    if strand == Strand.PLUS:
        upstream = genome.get_sequence_for_range(
            genome.wrap_position(start - 2), genome.wrap_position(start - 1)
        ).upper()
        downstream = genome.get_sequence_for_range(
            genome.wrap_position(end + 1), genome.wrap_position(end + 2)
        ).upper()
        donor = upstream
        acceptor = downstream
    else:
        upstream_fwd = genome.get_sequence_for_range(
            genome.wrap_position(start), genome.wrap_position(start + 1)
        ).upper()
        donor = upstream_fwd.translate(str.maketrans("ATGC", "TACG"))[::-1]

        downstream_fwd = genome.get_sequence_for_range(
            genome.wrap_position(end - 1), genome.wrap_position(end)
        ).upper()
        acceptor = downstream_fwd.translate(str.maketrans("ATGC", "TACG"))[::-1]

    if donor == "GT":
        score += 10
    elif donor == "GC":
        score += 5
    elif donor:
        score -= 20

    if acceptor == "AG":
        score += 10
    elif acceptor:
        score -= 20

    return score


def merge_exons_to_gene(
    gene_name: str,
    exon_hits: dict[int, list[tuple[int, int, Strand, float, int, int]]],
    config: dict,
    genome: GenomeSequence,
) -> GeneAnnotation | None:
    """Merge exon BLAST hits into a single gene annotation.

    Strategy:
    1. Check we have all expected exons
    2. Select best hit per exon (prioritize full-length matches, then highest identity)
    3. Calculate gene coordinates: start = min(exon starts), end = max(exon ends)
    4. Validate span <= max_span
    5. Create GeneAnnotation with merged exons

    Args:
        gene_name: Gene name
        exon_hits: Dict from search_exons_blastn() with (start, end, strand, identity, hit_length, expected_length)
        config: Gene config from TRANS_SPLICED_CONFIG
        genome: Genome sequence for boundary refinement

    Returns:
        GeneAnnotation with merged exons, or None if validation fails
    """
    expected_exons = config["exons"]
    max_span = config["max_span"]

    # Check we have all expected exons
    found_exon_nums = set(exon_hits.keys())
    expected_nums = set(range(1, expected_exons + 1))

    if not expected_nums.issubset(found_exon_nums):
        missing = expected_nums - found_exon_nums
        logger.debug(f"{gene_name}: missing exons {missing}, cannot merge")
        return None

    # Only select hits for expected exon numbers (ignore extra hits like exon_3 for 2-exon genes)
    best_exons: list[tuple[int, int, Strand, int]] = []  # (start, end, strand, exon_num)

    for exon_num in sorted(expected_nums):  # Only iterate expected exon numbers
        hits = exon_hits.get(exon_num, [])
        if not hits:
            logger.debug(f"{gene_name}: no hits for expected exon {exon_num}")
            return None

        # Sort by: 1) hit_length (prefer full-length), 2) identity, 3) splice-site consensus
        hits_with_score = []
        for h in hits:
            start, end, strand, identity, hit_length, expected_length = h
            coverage_ratio = hit_length / expected_length if expected_length > 0 else 0
            full_length_bonus = 100 if coverage_ratio >= 0.9 else 0
            base_score = full_length_bonus + identity * coverage_ratio
            # For hits that are clearly fragmented (coverage < 0.85), splice-site
            # scoring is unreliable because the BLASTn boundary may not align with
            # the true exon edge. Do not let splice penalties dominate hit selection
            # in these cases; they are valuable only for near-full-length hits.
            if coverage_ratio >= 0.85:
                splice_score = _score_splice_sites(genome, start, end, strand)
                score = base_score + splice_score
            else:
                score = base_score
            hits_with_score.append((h, score))

        # Sort by score descending
        hits_sorted = sorted(hits_with_score, key=lambda x: x[1], reverse=True)
        best_hit, best_score = hits_sorted[0]
        start, end, strand, identity, hit_length, expected_length = best_hit
        best_coverage = hit_length / expected_length if expected_length > 0 else 0

        # Check if the best hit is a fragmented/split exon
        # (some species have an intron within what the reference calls one exon)
        if best_coverage < 0.85 and len(hits_sorted) > 1:
            # Try to assemble non-overlapping hits that together cover >= 85%
            # Phase 4 fix: restrict to hits on the same strand as the best hit
            # to avoid pulling in reverse-complement false positives.
            best_strand = best_hit[2]
            pos_sorted = sorted(
                [(h, s) for h, s in hits_with_score if h[2] == best_strand],
                key=lambda x: min(x[0][0], x[0][1]),
            )
            max_exon_gap = config.get("max_exon_gap", 10000)
            # Phase 4 fix: anchor on best_hit and only accept nearby hits to
            # prevent distant false positives (e.g. NUMTs) from blowing up span.
            selected_hits = [best_hit]
            total_len = best_hit[4]
            best_start, best_end = sorted([best_hit[0], best_hit[1]])
            for h, score in pos_sorted:
                if h is best_hit:
                    continue
                h_start, h_end = sorted([h[0], h[1]])
                # Must be within max_exon_gap of at least one selected hit
                near_any = False
                for sel in selected_hits:
                    s_start, s_end = sorted([sel[0], sel[1]])
                    gap = min(
                        abs(h_start - s_end),
                        abs(h_end - s_start),
                    )
                    if gap <= max_exon_gap:
                        near_any = True
                        break
                if not near_any:
                    continue
                # Must not overlap with already selected (allow 10bp tolerance)
                overlaps = False
                for sel in selected_hits:
                    s_start, s_end = sorted([sel[0], sel[1]])
                    if min(h_end, s_end) - max(h_start, s_start) + 1 > 10:
                        overlaps = True
                        break
                if not overlaps and h[4] >= config.get("min_exon_bp", 15):
                    selected_hits.append(h)
                    total_len += h[4]
                    # Stop once we have sufficient coverage
                    if total_len / expected_length >= 0.85:
                        break

            combined_coverage = total_len / expected_length if expected_length > 0 else 0
            if combined_coverage >= 0.85:
                logger.info(
                    f"{gene_name}: reference exon {exon_num} splits into "
                    f"{len(selected_hits)} genome exons (coverage={combined_coverage:.2f})"
                )
                for h in selected_hits:
                    best_exons.append((h[0], h[1], h[2], exon_num))
                # For genes like cox2, where the reference bundles the first
                # two exons into one reference sequence, a split means the
                # species has one more exon than the reference count.
                if gene_name == "cox2" and len(selected_hits) >= 2:
                    expected_exons += len(selected_hits) - 1
                    expected_nums = set(range(1, expected_exons + 1))
                    logger.info(
                        f"{gene_name}: adaptive expected exons = {expected_exons}"
                    )
                continue

        best_exons.append((start, end, strand, exon_num))

        logger.debug(
            f"{gene_name} exon {exon_num}: {start}-{end} "
            f"({strand.symbol}, {identity:.1f}% identity, {hit_length}/{expected_length}bp, score={best_score:.1f})"
        )

    # Calculate gene boundaries
    # Phase 2: use circular span to correctly handle origin-crossing exons
    genome_length = len(genome.sequence)
    sorted_exons_for_span = sorted(best_exons, key=lambda e: e[0])
    max_gap = 0
    for i in range(len(sorted_exons_for_span) - 1):
        gap = sorted_exons_for_span[i + 1][0] - sorted_exons_for_span[i][1] - 1
        if gap > max_gap:
            max_gap = gap
    wrap_gap = sorted_exons_for_span[0][0] + (genome_length - sorted_exons_for_span[-1][1]) - 1
    if wrap_gap > max_gap:
        max_gap = wrap_gap
    gene_span = genome_length - max_gap

    gene_start = min(e[0] for e in best_exons)
    gene_end = max(e[1] for e in best_exons)

    # For genes with max_exon_gap constraint, try alternative hits if span is too large
    max_exon_gap = config.get("max_exon_gap")
    if max_exon_gap is not None and gene_span > max_exon_gap * 2:
        # Try to find alternative hit combinations with smaller span
        logger.debug(
            f"{gene_name}: span {gene_span}bp > 2x max_exon_gap {max_exon_gap}, "
            f"trying alternative hits"
        )

        # Get all hits for exon 1 (the anchor)
        exon1_hits = exon_hits.get(1, [])
        if exon1_hits:
            # Sort exon 1 hits by score (prioritize full-length)
            exon1_with_score = []
            for h in exon1_hits:
                coverage_ratio = h[4] / h[5] if h[5] > 0 else 0
                full_length_bonus = 100 if coverage_ratio >= 0.9 else 0
                score = full_length_bonus + h[3] * coverage_ratio
                exon1_with_score.append((h, score))
            exon1_sorted = sorted(exon1_with_score, key=lambda x: x[1], reverse=True)

            # Try each exon 1 hit as anchor, find compatible exon 2+ hits
            for e1_hit, e1_score in exon1_sorted[:3]:  # Try top 3 exon 1 hits
                e1_start, e1_end, e1_strand = e1_hit[0], e1_hit[1], e1_hit[2]

                # Find exon 2+ hits close to this exon 1
                alt_exons = [(e1_start, e1_end, e1_strand, 1)]

                for exon_num in range(2, expected_exons + 1):
                    hits_n = exon_hits.get(exon_num, [])
                    # Phase 2: use circular_span for origin-crossing distance checks
                    compatible = [
                        h for h in hits_n
                        if genome.circular_span(e1_end, h[0]) < max_exon_gap
                        or genome.circular_span(h[1], e1_start) < max_exon_gap
                    ]
                    if compatible:
                        # Take best compatible hit (by score)
                        compat_with_score = []
                        for h in compatible:
                            coverage_ratio = h[4] / h[5] if h[5] > 0 else 0
                            full_length_bonus = 100 if coverage_ratio >= 0.9 else 0
                            score = full_length_bonus + h[3] * coverage_ratio
                            compat_with_score.append((h, score))
                        compat_with_score.sort(key=lambda x: x[1], reverse=True)
                        best_compat = compat_with_score[0][0]
                        alt_exons.append((best_compat[0], best_compat[1], best_compat[2], exon_num))

                if len(alt_exons) == expected_exons:
                    # Phase 2: circular span for alt_exons too
                    alt_sorted = sorted(alt_exons, key=lambda e: e[0])
                    alt_max_gap = 0
                    for i in range(len(alt_sorted) - 1):
                        g = alt_sorted[i + 1][0] - alt_sorted[i][1] - 1
                        if g > alt_max_gap:
                            alt_max_gap = g
                    alt_wrap = alt_sorted[0][0] + (genome_length - alt_sorted[-1][1]) - 1
                    if alt_wrap > alt_max_gap:
                        alt_max_gap = alt_wrap
                    alt_span = genome_length - alt_max_gap
                    if alt_span < gene_span:
                        logger.info(
                            f"{gene_name}: using alternative hits with smaller span "
                            f"{alt_span}bp (was {gene_span}bp)"
                        )
                        best_exons = alt_exons
                        gene_start = min(e[0] for e in best_exons)
                        gene_end = max(e[1] for e in best_exons)
                        gene_span = alt_span
                        break

    # Validate span
    if gene_span > max_span:
        logger.warning(
            f"{gene_name}: merged span {gene_span}bp exceeds max {max_span}bp"
        )
        return None

    # Determine dominant strand for gene-level annotation
    # (exons retain their individual strands to support mixed-strand trans-splicing)
    strands = [e[2] for e in best_exons]
    if len(set(strands)) > 1:
        logger.warning(f"{gene_name}: exons on mixed strands, using most common for gene feature")
        strand = max(set(strands), key=strands.count)
    else:
        strand = strands[0]

    # Sort exons by genomic position in transcription order
    # Plus strand: 5'->3' is ascending start coordinate
    # Minus strand: 5'->3' is descending end coordinate
    # Mixed strand (e.g. plant mitochondrial nad2): preserve exon number order,
    # which reflects the known biological transcription order for trans-spliced genes
    if len(set(strands)) > 1:
        best_exons.sort(key=lambda e: e[3])  # sort by exon_num
    elif strand == Strand.PLUS:
        best_exons.sort(key=lambda e: e[0])
    else:
        best_exons.sort(key=lambda e: e[1], reverse=True)

    exons = []
    cumulative_len = 0
    for i, e in enumerate(best_exons, 1):
        phase = cumulative_len % 3
        exons.append(ExonRecord(start=e[0], end=e[1], strand=e[2], number=i, phase=phase))
        cumulative_len += e[1] - e[0] + 1

    # Refine boundaries for problematic genes
    exons = refine_exon_boundaries_with_codons(exons, genome, strand, gene_name)

    # Create annotation
    annotation = GeneAnnotation(
        gene_name=gene_name,
        gene_type="CDS",
        exons=exons,
        strand=strand,
        notes=[f"Merged from {len(exons)} exons via BLASTn"],
        source_method="BLAST",
    )

    logger.info(
        f"{gene_name}: merged {len(exons)} exons, span={gene_start}-{gene_end} "
        f"({gene_span}bp)"
    )

    return annotation


def refine_exon_boundaries_with_codons(
    exons: list[ExonRecord],
    genome: GenomeSequence,
    strand: Strand,
    gene_name: str,
) -> list[ExonRecord]:
    """Refine exon boundaries using start/stop codons.

    For genes with known boundary issues (cox2, nad6), check:
    1. Exon ends should align with stop codon (TAA, TAG, TGA)
    2. Adjust boundaries within small tolerance

    Args:
        exons: Current exon records (sorted by position)
        genome: Genome sequence
        strand: Gene strand
        gene_name: Gene name

    Returns:
        Refined exon records
    """
    # Genes with known boundary issues
    problematic_genes = {"cox2", "nad6", "atp6", "rps3", "nad5"}

    if gene_name.lower() not in problematic_genes:
        return exons

    stop_codons = ["TAA", "TAG", "TGA"]
    refined = []

    # Only the terminal exon should contain the stop codon.
    # For plus strand: terminal exon has the largest end coordinate.
    # For minus strand: terminal exon has the smallest start coordinate.
    if strand == Strand.PLUS:
        terminal_exon = max(exons, key=lambda e: e.end)
    else:
        terminal_exon = min(exons, key=lambda e: e.start)

    for exon in exons:
        # Only refine the terminal exon; internal exons keep BLAST-derived boundaries
        if exon is not terminal_exon:
            refined.append(exon)
            continue

        if strand == Strand.PLUS:
            # If the last 3 bases already contain a stop codon, keep boundary
            last_codon = genome.sequence[exon.end - 3 : exon.end].upper()
            if last_codon in stop_codons:
                refined.append(exon)
                continue

            region_end = min(exon.end + 50, len(genome.sequence))
            region = genome.sequence[exon.end:region_end]
            for offset in range(0, min(50, len(region))):
                codon = region[offset:offset+3].upper() if offset+3 <= len(region) else ""
                if codon in stop_codons:
                    new_end = exon.end + offset + 3
                    new_start = exon.start
                    break
            else:
                refined.append(exon)
                continue
        else:
            # For minus strand, check first 3 bases (reverse complement)
            first_codon = str(Seq(genome.sequence[exon.start:exon.start+3]).reverse_complement()).upper()
            if first_codon in stop_codons:
                refined.append(exon)
                continue

            region_start = max(0, exon.start - 50)
            region = str(Seq(genome.sequence[region_start:exon.start]).reverse_complement())
            for offset in range(0, min(50, len(region))):
                codon = region[offset:offset+3].upper() if offset+3 <= len(region) else ""
                if codon in stop_codons:
                    new_start = exon.start - offset - 3
                    new_end = exon.end
                    break
            else:
                refined.append(exon)
                continue

        if new_end != exon.end or new_start != exon.start:
            logger.debug(
                f"{gene_name} exon {exon.number}: refined boundary "
                f"by {abs(new_end - exon.end) + abs(new_start - exon.start)}bp to stop codon"
            )
            refined.append(ExonRecord(
                start=new_start,
                end=new_end,
                strand=exon.strand,
                number=exon.number,
            ))
        else:
            refined.append(exon)

    return refined


def annotate_trans_spliced_genes(
    genome: GenomeSequence,
    db_manager: DBManager,
    existing_annotations: dict[str, GeneAnnotation],
) -> dict[str, GeneAnnotation]:
    """Main entry point: annotate trans-spliced genes using BLASTn exon search.

    For genes in TRANS_SPLICED_CONFIG:
    1. Skip if already has enough exons
    2. Find exon reference file
    3. Run BLASTn search
    4. Merge exons into gene annotation

    Args:
        genome: Genome sequence
        db_manager: Database manager
        existing_annotations: Current annotations (will be updated)

    Returns:
        Updated annotations dict
    """
    blastn = shutil.which("blastn")
    if not blastn:
        logger.warning("blastn not available, skipping trans-spliced annotation")
        return existing_annotations

    # Get dynamic configuration based on genome length
    genome_length = len(genome.sequence)
    trans_spliced_config = get_dynamic_trans_spliced_config(genome_length)
    logger.info(f"Using dynamic trans-spliced config for {genome_length}bp genome")

    hmm_discarded = set()  # Track genes where HMM was discarded due to large span

    for gene_name, config in trans_spliced_config.items():
        # Check if gene is already annotated
        already_found = gene_name in existing_annotations

        if already_found:
            current = existing_annotations[gene_name]

            # Check HMM annotation span - if too large, it may be wrong
            # Phase 2: use circular span to correctly handle origin-crossing exons
            hmm_span = _circular_gene_span(current.exons, genome_length)
            max_span = config["max_span"]

            # If HMM span exceeds max_span, discard and use BLASTn only
            if hmm_span > max_span:
                logger.warning(
                    f"{gene_name}: HMM span {hmm_span}bp > max {max_span}bp, "
                    f"discarding HMM result and using BLASTn exon search"
                )
                # Remove from dict to force BLASTn search
                del existing_annotations[gene_name]
                already_found = False
                hmm_discarded.add(gene_name)
            elif len(current.exons) >= config["exons"]:
                # Only force BLASTn refinement for genes with known systematic
                # boundary drift (e.g. nad7). For others, trust existing annotation.
                if gene_name not in {"nad1", "nad7", "cox2", "nad4"}:
                    logger.debug(f"{gene_name}: already has {len(current.exons)} exons, skipping")
                    continue
                logger.info(
                    f"{gene_name}: already has {len(current.exons)} exons, "
                    f"attempting BLASTn refinement for boundary accuracy"
                )
                # Fall through to BLASTn search so reference-exon based boundaries
                # can replace or confirm the HMM-derived ones.
            else:
                logger.info(
                    f"{gene_name}: has {len(current.exons)} exons, expected {config['exons']}. "
                    f"Attempting BLASTn exon search to find missing exons."
                )

        if not already_found:
            if gene_name in hmm_discarded:
                logger.info(
                    f"{gene_name}: HMM result discarded. "
                    f"Attempting BLASTn exon search for accurate position."
                )
            else:
                # Gene not found by HMM - try BLASTn exon search anyway
                logger.info(
                    f"{gene_name}: not found by HMM search. "
                    f"Attempting BLASTn exon search for trans-spliced gene."
                )

        # Find exon reference file
        exon_ref = find_exon_reference_file(gene_name, db_manager)
        if not exon_ref:
            logger.debug(f"No exon reference file for {gene_name}, skipping")
            continue

        # Run BLASTn search
        exon_hits = search_exons_blastn(gene_name, genome, exon_ref, blastn)

        if not exon_hits:
            logger.debug(f"{gene_name}: no BLASTn hits found")
            continue

        # Merge exons into gene
        merged = merge_exons_to_gene(gene_name, exon_hits, config, genome)

        if merged:
            existing_annotations[gene_name] = merged
            logger.info(f"{gene_name}: successfully merged {len(merged.exons)} exons")

    return existing_annotations