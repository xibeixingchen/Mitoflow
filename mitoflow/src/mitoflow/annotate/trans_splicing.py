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
import shutil
import subprocess
import tempfile
from pathlib import Path

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
    "nad7": {"exons": 4, "min_exon_bp": 30, "note": "4 cis-spliced exons"},
    # Multi-exon genes with cis-splicing (exons close together)
    "cox2": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons"},
    "rpl2": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons"},
    "rps3": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons"},
    "ccmFC": {"exons": 2, "min_exon_bp": 50, "note": "2 cis-spliced exons"},
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
    ref_dir = db_manager.blast_ref_dir

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


def _find_exon_reference(gene_name: str, ref_dir: Path) -> Path | None:
    """Find exon reference file for a gene.

    Looks for:
    1. {gene_name}_exons.fasta (individual exon sequences)
    2. {gene_name}.CDS.fasta (full CDS sequence)
    """
    # Check for exon-specific reference
    exon_ref = ref_dir / f"{gene_name}_exons.fasta"
    if exon_ref.exists():
        return exon_ref

    # Check for CDS reference
    cds_ref = ref_dir / f"{gene_name}.CDS.fasta"
    if cds_ref.exists():
        return cds_ref

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