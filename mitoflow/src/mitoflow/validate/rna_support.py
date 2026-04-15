"""RNA-seq BAM support validation for manual inspection.

Generates IGV/Tablet-compatible tracks and scans suspicious sites
(start/stop codons, splice boundaries) for visual confirmation.

Inspired by PMGA manual BAM depth validation workflow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ..models.gene import GeneAnnotation, Strand

logger = logging.getLogger(__name__)

try:
    import pysam

    PYSAM_AVAILABLE = True
except ImportError:
    PYSAM_AVAILABLE = False


@dataclass
class SuspiciousSite:
    """A site flagged for manual RNA-seq verification."""

    gene_name: str
    site_type: str  # start_codon, stop_codon, splice_donor, splice_acceptor
    position: int
    window_start: int
    window_end: int
    mean_depth: float
    min_depth: int
    reason: str


def _get_contig(bam_path: Path, contig: Optional[str] = None) -> str:
    """Resolve contig name from BAM header."""
    with pysam.AlignmentFile(str(bam_path), "rb") as bam:
        if contig is not None:
            return contig
        if bam.nreferences == 0:
            raise ValueError("BAM file has no references")
        return bam.references[0]


def _load_depth_array(bam_path: Path, contig: str) -> np.ndarray:
    """Load per-base depth as a 1-D numpy array (0-based indexing)."""
    with pysam.AlignmentFile(str(bam_path), "rb") as bam:
        coverage = bam.count_coverage(reference=contig, read_callback="all")
    return np.sum(coverage, axis=0, dtype=np.int32)


def bam_to_bedgraph(
    bam_path: Path,
    output_path: Path,
    contig: Optional[str] = None,
) -> Path:
    """Export per-base read depth as an IGV-compatible bedGraph file.

    Uses run-length encoding of equal depths to keep file size small.
    """
    if not PYSAM_AVAILABLE:
        raise ImportError("pysam is required for RNA-seq BAM validation")

    contig = _get_contig(bam_path, contig)
    depth = _load_depth_array(bam_path, contig)

    with open(output_path, "w") as fh:
        fh.write(
            'track type=bedGraph name="RNA-seq depth" visibility=full color=0,0,128\n'
        )
        if len(depth) == 0:
            return output_path

        start = 0
        curr = int(depth[0])
        for i in range(1, len(depth)):
            if int(depth[i]) != curr:
                fh.write(f"{contig}\t{start}\t{i}\t{curr}\n")
                start = i
                curr = int(depth[i])
        fh.write(f"{contig}\t{start}\t{len(depth)}\t{curr}\n")

    logger.info("bedGraph written: %s", output_path)
    return output_path


def extract_splice_junctions(
    bam_path: Path,
    output_path: Path,
    contig: Optional[str] = None,
    min_depth: int = 2,
) -> Path:
    """Extract splice junctions from CIGAR N operations and write BED12 track.

    Output format follows the TopHat/RegTools junction BED convention
    (compatible with IGV/Tablet).
    """
    if not PYSAM_AVAILABLE:
        raise ImportError("pysam is required for RNA-seq BAM validation")

    contig = _get_contig(bam_path, contig)
    junctions: dict[tuple[str, int, int, str], int] = {}

    with pysam.AlignmentFile(str(bam_path), "rb") as bam:
        for read in bam.fetch(reference=contig):
            if read.is_unmapped:
                continue
            ref_pos = read.reference_start
            strand = "-" if read.is_reverse else "+"
            for op, length in read.cigartuples:
                if op == 3:  # N = skipped region (intron)
                    jstart = ref_pos
                    jend = ref_pos + length
                    key = (contig, jstart, jend, strand)
                    junctions[key] = junctions.get(key, 0) + 1
                if op in (0, 2, 3, 7, 8):  # consumes reference
                    ref_pos += length

    with open(output_path, "w") as fh:
        fh.write(
            'track name="Splice Junctions" description="RNA-seq splice junctions" '
            'visibility=2 itemRgb="On"\n'
        )
        for (chrom, jstart, jend, strand), count in sorted(junctions.items()):
            if count < min_depth:
                continue
            name = f"{chrom}:{jstart + 1}-{jend}"
            score = min(count, 1000)
            rgb = "50,50,200" if strand == "+" else "200,50,50"
            block_sizes = "1,1"
            block_starts = f"0,{jend - jstart - 1}"
            fh.write(
                f"{chrom}\t{jstart}\t{jend}\t{name}\t{score}\t{strand}\t"
                f"{jstart}\t{jend}\t{rgb}\t2\t{block_sizes}\t{block_starts}\n"
            )

    logger.info("Junction BED written: %s", output_path)
    return output_path


def scan_suspicious_sites(
    bam_path: Path,
    annotations: list[GeneAnnotation],
    genome_length: int,
    output_path: Path,
    contig: Optional[str] = None,
    window: int = 10,
    depth_ratio_threshold: float = 0.2,
) -> list[SuspiciousSite]:
    """Scan annotation boundaries for coverage anomalies.

    Flags start/stop codons and splice sites where coverage drops to zero
    or falls below a fraction of the genome-wide mean.
    """
    if not PYSAM_AVAILABLE:
        raise ImportError("pysam is required for RNA-seq BAM validation")

    contig = _get_contig(bam_path, contig)
    depth = _load_depth_array(bam_path, contig)
    mean_depth = float(np.mean(depth)) if len(depth) > 0 else 0.0

    def _depth_at(pos: int) -> int:
        """Fetch depth at a 1-based position (handles circular wrap)."""
        idx = (pos - 1) % genome_length
        return int(depth[idx]) if idx < len(depth) else 0

    def _window_depths(center: int, radius: int) -> list[int]:
        return [_depth_at(((center - 1 + o) % genome_length) + 1) for o in range(-radius, radius + 1)]

    suspicious: list[SuspiciousSite] = []

    for gene in annotations:
        sorted_exons = sorted(gene.exons, key=lambda e: e.start)

        # Start / stop codon positions on the genome
        if gene.strand == Strand.PLUS:
            start_pos = sorted_exons[0].start
            stop_pos = sorted_exons[-1].end
        else:
            start_pos = sorted_exons[-1].end
            stop_pos = sorted_exons[0].start

        for site_type, pos in [("start_codon", start_pos), ("stop_codon", stop_pos)]:
            depths = _window_depths(pos, window)
            min_d = min(depths)
            mean_d = sum(depths) / len(depths)
            reason: Optional[str] = None
            if min_d == 0:
                reason = "zero coverage"
            elif mean_depth > 0 and mean_d < mean_depth * depth_ratio_threshold:
                reason = f"low coverage (mean={mean_d:.1f}, genome_mean={mean_depth:.1f})"

            if reason:
                suspicious.append(
                    SuspiciousSite(
                        gene_name=gene.gene_name,
                        site_type=site_type,
                        position=pos,
                        window_start=((pos - 1 - window) % genome_length) + 1,
                        window_end=((pos - 1 + window) % genome_length) + 1,
                        mean_depth=mean_d,
                        min_depth=min_d,
                        reason=reason,
                    )
                )

        # Splice boundaries
        if len(sorted_exons) > 1:
            for i in range(len(sorted_exons) - 1):
                left = sorted_exons[i]
                right = sorted_exons[i + 1]
                if gene.strand == Strand.PLUS:
                    pairs = [
                        ("splice_donor", left.end),
                        ("splice_acceptor", right.start),
                    ]
                else:
                    pairs = [
                        ("splice_donor", right.start),
                        ("splice_acceptor", left.end),
                    ]

                for site_type, pos in pairs:
                    depths = _window_depths(pos, window)
                    min_d = min(depths)
                    mean_d = sum(depths) / len(depths)
                    reason = None
                    if min_d == 0:
                        reason = "zero coverage"
                    elif mean_depth > 0 and mean_d < mean_depth * depth_ratio_threshold:
                        reason = f"low coverage (mean={mean_d:.1f}, genome_mean={mean_depth:.1f})"

                    if reason:
                        suspicious.append(
                            SuspiciousSite(
                                gene_name=gene.gene_name,
                                site_type=site_type,
                                position=pos,
                                window_start=((pos - 1 - window) % genome_length) + 1,
                                window_end=((pos - 1 + window) % genome_length) + 1,
                                mean_depth=mean_d,
                                min_depth=min_d,
                                reason=reason,
                            )
                        )

    with open(output_path, "w") as fh:
        fh.write(
            "gene_name\tsite_type\tposition\twindow_start\twindow_end\t"
            "mean_depth\tmin_depth\treason\n"
        )
        for site in suspicious:
            fh.write(
                f"{site.gene_name}\t{site.site_type}\t{site.position}\t"
                f"{site.window_start}\t{site.window_end}\t"
                f"{site.mean_depth:.1f}\t{site.min_depth}\t{site.reason}\n"
            )

    logger.info("Suspicious sites written: %s (%d sites)", output_path, len(suspicious))
    return suspicious


def validate_rna_support(
    bam_path: Path,
    gb_path: Path,
    genome,
    output_dir: Path,
    prefix: str = "mitoflow",
    window: int = 10,
    min_junction_depth: int = 2,
    depth_ratio_threshold: float = 0.2,
) -> dict[str, Path]:
    """Run full RNA-seq validation workflow.

    Args:
        bam_path: Path to RNA-seq BAM file (must be indexed).
        gb_path: GenBank annotation file.
        genome: GenomeSequence object (used for length / circular coords).
        output_dir: Directory to write outputs.
        prefix: Prefix for output filenames.
        window: Number of bases on each side of a boundary to scan.
        min_junction_depth: Minimum read support to keep a junction.
        depth_ratio_threshold: Fraction of mean depth below which a site is flagged.

    Returns:
        Mapping of output type -> file path.
    """
    if not PYSAM_AVAILABLE:
        raise ImportError(
            "pysam is required for RNA-seq BAM validation. "
            "Install with: pip install pysam"
        )

    from Bio import SeqIO
    from ..models.gene import ExonRecord

    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse GenBank into GeneAnnotation objects
    record = next(SeqIO.parse(str(gb_path), "genbank"))
    annotations: list[GeneAnnotation] = []
    for feat in record.features:
        if feat.type != "CDS":
            continue
        gname = feat.qualifiers.get(
            "gene", feat.qualifiers.get("locus_tag", ["unknown"])
        )[0]

        exons: list[ExonRecord] = []
        if hasattr(feat.location, "parts") and len(feat.location.parts) > 1:
            for idx, part in enumerate(feat.location.parts, start=1):
                strand_val = Strand.PLUS if (part.strand or 1) == 1 else Strand.MINUS
                exons.append(
                    ExonRecord(
                        start=int(part.start) + 1,
                        end=int(part.end),
                        strand=strand_val,
                        number=idx,
                    )
                )
        else:
            strand_val = Strand.PLUS if (feat.location.strand or 1) == 1 else Strand.MINUS
            exons.append(
                ExonRecord(
                    start=int(feat.location.start) + 1,
                    end=int(feat.location.end),
                    strand=strand_val,
                    number=1,
                )
            )

        annotations.append(
            GeneAnnotation(
                gene_name=gname,
                exons=exons,
                strand=exons[0].strand,
            )
        )

    contig = _get_contig(bam_path)

    bedgraph_path = output_dir / f"{prefix}_rna_depth.bedgraph"
    bam_to_bedgraph(bam_path, bedgraph_path, contig=contig)

    junction_path = output_dir / f"{prefix}_splice_junctions.bed"
    extract_splice_junctions(
        bam_path, junction_path, contig=contig, min_depth=min_junction_depth
    )

    suspicious_path = output_dir / f"{prefix}_suspicious_sites.tsv"
    scan_suspicious_sites(
        bam_path=bam_path,
        annotations=annotations,
        genome_length=genome.length,
        output_path=suspicious_path,
        contig=contig,
        window=window,
        depth_ratio_threshold=depth_ratio_threshold,
    )

    return {
        "bedgraph": bedgraph_path,
        "junctions": junction_path,
        "suspicious_sites": suspicious_path,
    }
