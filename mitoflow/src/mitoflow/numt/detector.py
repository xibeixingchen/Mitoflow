"""NUMT (Nuclear Mitochondrial DNA Segment) detection.

Detects mitochondrial DNA fragments inserted into the nuclear genome
by BLAST comparison. Identifies MTPT vs NUMT based on flanking nuclear
genes and insertion context.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NUMTRegion:
    """A NUMT insertion region in the nuclear genome."""
    chr_id: str
    start: int            # 1-based
    end: int
    mito_start: int       # corresponding mt region
    mito_end: int
    identity: float       # %
    length: int
    evalue: float
    mito_genes_covered: list[str] = field(default_factory=list)
    fragment_category: str = ""   # intact / partial / chimeric

    def to_bed_line(self) -> str:
        genes = ",".join(self.mito_genes_covered) if self.mito_genes_covered else "none"
        return (
            f"{self.chr_id}\t{self.start - 1}\t{self.end}\t"
            f"NUMT_{self.start}\t{self.identity:.1f}\t+\t{genes}\t{self.fragment_category}"
        )


@dataclass
class NUMTResult:
    """NUMT detection result."""
    regions: list[NUMTRegion] = field(default_factory=list)
    nuclear_genome_length: int = 0
    mito_genome_length: int = 0
    tool_used: str = "BLAST"

    @property
    def total_numts(self) -> int:
        return len(self.regions)

    @property
    def total_numt_bp(self) -> int:
        return sum(r.length for r in self.regions)

    @property
    def coverage_pct(self) -> float:
        return self.total_numt_bp / self.mito_genome_length * 100 if self.mito_genome_length > 0 else 0.0

    def by_category(self) -> dict[str, list[NUMTRegion]]:
        cats: dict[str, list[NUMTRegion]] = {}
        for r in self.regions:
            cats.setdefault(r.fragment_category, []).append(r)
        return cats

    def summary(self) -> str:
        lines = [
            f"NUMT Detection ({self.tool_used})",
            f"  Total NUMTs: {self.total_numts}",
            f"  Total NUMT bp: {self.total_numt_bp:,}",
            f"  Mito coverage: {self.coverage_pct:.2f}%",
        ]
        for cat, regions in sorted(self.by_category().items()):
            lines.append(f"  {cat}: {len(regions)}")
        return "\n".join(lines)


def detect_numts(
    mito_fasta: Path,
    nuclear_fasta: Path,
    output_dir: Path,
    threads: int = 4,
    min_identity: float = 80.0,
    min_length: int = 200,
    mito_gbk: Path | None = None,
) -> NUMTResult:
    """Detect NUMTs by BLASTing mitochondrial genome against nuclear genome.

    Args:
        mito_fasta: Mitochondrial genome FASTA
        nuclear_fasta: Nuclear genome FASTA
        output_dir: Output directory
        threads: BLAST threads
        min_identity: Minimum identity %
        min_length: Minimum alignment length (bp)
        mito_gbk: Optional mitochondrial GenBank file for gene annotation

    Returns:
        NUMTResult
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    blastn = shutil.which("blastn")
    makeblastdb = shutil.which("makeblastdb")

    if not blastn or not makeblastdb:
        logger.warning("BLAST+ not found, cannot detect NUMTs")
        return NUMTResult(tool_used="unavailable")

    # Build nuclear BLAST database
    db_path = output_dir / "nuclear_db"
    subprocess.run(
        [makeblastdb, "-in", str(nuclear_fasta), "-dbtype", "nucl",
         "-out", str(db_path)],
        capture_output=True, text=True, timeout=600,
    )

    # BLAST mito vs nuclear
    outfmt = "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore"
    result = subprocess.run(
        [blastn, "-query", str(mito_fasta), "-db", str(db_path),
         "-outfmt", outfmt, "-evalue", "1e-10",
         "-dust", "no", "-word_size", "15",
         "-num_threads", str(threads),
         "-perc_identity", str(min_identity)],
        capture_output=True, text=True, timeout=1800,
    )

    if result.returncode != 0:
        logger.warning(f"BLASTN failed: {result.stderr[:200]}")
        return NUMTResult(tool_used="BLAST_failed")

    # Parse results
    from Bio import SeqIO
    mito_len = sum(len(r.seq) for r in SeqIO.parse(str(mito_fasta), "fasta"))
    nuc_len = sum(len(r.seq) for r in SeqIO.parse(str(nuclear_fasta), "fasta"))

    regions = []
    seen = set()

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 12:
            continue

        try:
            length = int(parts[3])
            identity = float(parts[2])
            if length < min_length:
                continue

            chr_id = parts[1]
            nuc_s, nuc_e = int(parts[8]), int(parts[9])
            mito_s, mito_e = int(parts[6]), int(parts[7])

            if nuc_s > nuc_e:
                nuc_s, nuc_e = nuc_e, nuc_s
            if mito_s > mito_e:
                mito_s, mito_e = mito_e, mito_s

            # Deduplicate overlapping hits
            key = (chr_id, nuc_s // 1000, nuc_e // 1000)
            if key in seen:
                continue
            seen.add(key)

            evalue = float(parts[10])

            # Classify
            ratio = length / (mito_e - mito_s + 1) if mito_e > mito_s else 0
            if ratio > 0.9:
                category = "intact"
            elif ratio > 0.5:
                category = "partial"
            else:
                category = "chimeric"

            regions.append(NUMTRegion(
                chr_id=chr_id,
                start=nuc_s,
                end=nuc_e,
                mito_start=mito_s,
                mito_end=mito_e,
                identity=identity,
                length=length,
                evalue=evalue,
                fragment_category=category,
            ))
        except (ValueError, IndexError):
            continue

    # Remove overlapping NUMTs (keep best)
    regions = _remove_overlaps(regions)

    # Annotate mito genes covered by each NUMT
    if mito_gbk and mito_gbk.exists():
        _annotate_mito_genes(regions, mito_gbk)

    return NUMTResult(
        regions=regions,
        nuclear_genome_length=nuc_len,
        mito_genome_length=mito_len,
    )


def _remove_overlaps(regions: list[NUMTRegion]) -> list[NUMTRegion]:
    """Remove overlapping NUMT calls, keep highest identity."""
    if not regions:
        return []
    regions.sort(key=lambda r: r.identity, reverse=True)
    kept = []
    for r in regions:
        if not any(
            r.start <= k.end and r.end >= k.start and r.chr_id == k.chr_id
            for k in kept
        ):
            kept.append(r)
    return sorted(kept, key=lambda r: (r.chr_id, r.start))


def _annotate_mito_genes(regions: list[NUMTRegion], mito_gbk: Path) -> None:
    """Annotate which mitochondrial genes each NUMT covers.

    Reads gene features from a GenBank file and checks overlap with
    each NUMT's mitochondrial coordinates.
    """
    from Bio import SeqIO

    genes = []
    for rec in SeqIO.parse(str(mito_gbk), "genbank"):
        for feat in rec.features:
            if feat.type in ("gene", "CDS", "tRNA", "rRNA"):
                name = (
                    feat.qualifiers.get("gene", [None])[0]
                    or feat.qualifiers.get("product", [None])[0]
                    or feat.qualifiers.get("locus_tag", [f"feat_{feat.location.start}"])[0]
                )
                genes.append((int(feat.location.start) + 1, int(feat.location.end), name))

    for r in regions:
        covered = []
        for g_start, g_end, g_name in genes:
            # Check overlap: NUMT covers [mito_start, mito_end]
            overlap_start = max(r.mito_start, g_start)
            overlap_end = min(r.mito_end, g_end)
            if overlap_end >= overlap_start:
                covered.append(g_name)
        r.mito_genes_covered = covered


def write_numt_output(result: NUMTResult, output_dir: Path, name: str) -> dict[str, Path]:
    """Write NUMT results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    tsv_path = output_dir / f"{name}_numt.tsv"
    with open(tsv_path, "w") as f:
        f.write("Chr\tStart\tEnd\tMitoStart\tMitoEnd\tLength\tIdentity\tCategory\tMitoGenes\n")
        for r in result.regions:
            genes = ",".join(r.mito_genes_covered) or "none"
            f.write(
                f"{r.chr_id}\t{r.start}\t{r.end}\t{r.mito_start}\t{r.mito_end}\t"
                f"{r.length}\t{r.identity:.1f}\t{r.fragment_category}\t{genes}\n"
            )
    files["tsv"] = tsv_path

    bed_path = output_dir / f"{name}_numt.bed"
    with open(bed_path, "w") as f:
        for r in result.regions:
            f.write(r.to_bed_line() + "\n")
    files["bed"] = bed_path

    return files
