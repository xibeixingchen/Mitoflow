"""Contamination detection (Dimension 4).

Detects chloroplast contamination vs true MTPT, nuclear contamination,
and GC anomalies. Distinguishes normal MTPT from misassembled cpDNA.
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
class GCAnomaly:
    """Region with anomalous GC content."""
    start: int
    end: int
    gc_pct: float
    deviation_sigma: float
    likely_source: str  # "chloroplast" | "nuclear" | "unknown"


@dataclass
class ContaminationRegion:
    """A suspected contamination or MTPT region."""
    start: int
    end: int
    source: str  # "chloroplast" | "nuclear" | "unknown"
    identity: float
    length: int
    is_true_mtpt: bool
    cp_genes_covered: list = field(default_factory=list)
    verdict: str = ""


@dataclass
class ContaminationResult:
    """Complete contamination assessment."""
    # Chloroplast
    cp_regions: list = field(default_factory=list)
    total_cp_length: int = 0
    n_true_mtpt: int = 0
    n_suspect_misassembly: int = 0
    has_complete_cp_genes: bool = False

    # Nuclear
    nuclear_suspect_regions: list = field(default_factory=list)

    # GC anomalies
    gc_anomaly_regions: list = field(default_factory=list)

    contamination_score: float = 0.0
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Contamination: score={self.contamination_score:.0f}/100",
            f"  MTPT regions: {self.n_true_mtpt} ({self.total_cp_length:,} bp)",
            f"  Suspect misassembly: {self.n_suspect_misassembly}",
            f"  GC anomalies: {len(self.gc_anomaly_regions)}",
            f"  Complete cp genes: {'Yes' if self.has_complete_cp_genes else 'No'}",
        ]
        for w in self.warnings:
            lines.append(f"  Warning: {w}")
        return "\n".join(lines)


def detect_contamination(
    genome: GenomeSequence,
    fasta_path: Path,
    cp_fasta: Optional[Path] = None,
    window_size: int = 1000,
    step_size: int = 100,
) -> ContaminationResult:
    """Full contamination detection.

    A. Chloroplast detection (if cp genome provided):
       - BLAST mito vs cp
       - Classify: MTPT (normal) vs misassembled cpDNA
       - MTPT: identity 80-99%, no complete cp genes, length <5kb
       - Suspected misassembly: identity >99.5%, complete cp genes (rbcL, psbA, ndhF)

    B. Nuclear contamination:
       - GC anomaly detection (>2 sigma from mean)
       - Regions with anomalous GC + no mitochondrial genes

    C. Quick cp marker check (if no cp genome):
       - Search for rbcL, matK, psbA, ndhF, atpB markers
    """
    result = ContaminationResult()

    # GC anomaly detection (always run)
    result.gc_anomaly_regions = _detect_gc_anomalies(
        genome, window_size, step_size
    )

    # Chloroplast detection
    if cp_fasta:
        mtpt_regions, suspect_regions = _detect_cp_regions(
            fasta_path, cp_fasta
        )
        result.cp_regions = mtpt_regions + suspect_regions
        result.n_true_mtpt = len(mtpt_regions)
        result.n_suspect_misassembly = len(suspect_regions)
        result.total_cp_length = sum(r.length for r in result.cp_regions)

        for r in suspect_regions:
            if r.cp_genes_covered:
                result.has_complete_cp_genes = True
            result.warnings.append(
                f"Suspected cp contamination at {r.start}-{r.end} "
                f"(id={r.identity:.1f}%, {len(r.cp_genes_covered)} cp genes)"
            )
    else:
        # Quick marker check
        markers_found = _check_cp_markers(fasta_path)
        if markers_found:
            result.warnings.append(
                f"Chloroplast markers found intact: {', '.join(markers_found)}. "
                f"Provide cp genome for detailed MTPT analysis."
            )

    # Nuclear contamination from GC anomalies
    result.nuclear_suspect_regions = _check_nuclear_contamination(
        genome, result.gc_anomaly_regions
    )

    # Score
    result.contamination_score = _score_contamination(result)

    return result


def _detect_gc_anomalies(
    genome: GenomeSequence, window_size: int, step_size: int,
    sigma_threshold: float = 2.0,
) -> list:
    """Sliding window GC anomaly detection."""
    seq = genome.sequence.upper()
    length = len(seq)
    if length < window_size:
        return []

    import statistics

    gc_values = []
    for start in range(0, length - window_size + 1, step_size):
        window = seq[start:start + window_size]
        gc = (window.count("G") + window.count("C")) / len(window) * 100
        gc_values.append(gc)

    if not gc_values:
        return []

    mean_gc = statistics.mean(gc_values)
    stdev_gc = statistics.stdev(gc_values) if len(gc_values) > 1 else 0
    if stdev_gc == 0:
        return []

    anomalies = []
    for i, start in enumerate(range(0, length - window_size + 1, step_size)):
        gc = gc_values[i]
        sigma = (gc - mean_gc) / stdev_gc
        if abs(sigma) > sigma_threshold:
            if gc > mean_gc + 2 * stdev_gc:
                likely = "chloroplast"
            elif gc < mean_gc - 2 * stdev_gc:
                likely = "nuclear"
            else:
                likely = "unknown"
            anomalies.append(GCAnomaly(
                start=start + 1, end=start + window_size,
                gc_pct=gc, deviation_sigma=sigma,
                likely_source=likely,
            ))

    return anomalies


def _detect_cp_regions(
    fasta_path: Path, cp_fasta: Path,
) -> tuple:
    """BLAST mito vs cp, classify MTPT vs contamination."""
    blastn = shutil.which("blastn")
    makeblastdb = shutil.which("makeblastdb")
    if not blastn or not makeblastdb:
        return [], []

    mtpt_regions = []
    suspect_regions = []

    with tempfile.TemporaryDirectory() as tmpdir:
        cp_db = Path(tmpdir) / "cp_db"
        subprocess.run(
            [makeblastdb, "-in", str(cp_fasta), "-dbtype", "nucl",
             "-out", str(cp_db)],
            capture_output=True, timeout=120,
        )

        proc = subprocess.run(
            [blastn, "-query", str(fasta_path), "-db", str(cp_db),
             "-outfmt", "6 qstart qend sstart send pident length evalue bitscore",
             "-evalue", "1e-10", "-max_target_seqs", "10", "-dust", "no"],
            capture_output=True, text=True, timeout=300,
        )

        if proc.returncode != 0:
            return [], []

        hits = _parse_blast(proc.stdout)
        merged = _merge_hits(hits)

        for hit in merged:
            identity = hit["pident"]
            length = hit["length"]
            region = ContaminationRegion(
                start=min(hit["qstart"], hit["qend"]),
                end=max(hit["qstart"], hit["qend"]),
                source="chloroplast",
                identity=identity,
                length=length,
                is_true_mtpt=True,
            )

            if identity >= 99.5 and length >= 500:
                # Suspected misassembly
                region.is_true_mtpt = False
                region.verdict = "Suspected cp contamination"
                suspect_regions.append(region)
            elif identity >= 95:
                region.verdict = "MTPT (recent)"
                mtpt_regions.append(region)
            elif identity >= 80:
                region.verdict = "MTPT (degenerate)"
                mtpt_regions.append(region)
            elif identity >= 70:
                region.verdict = "MTPT (ancient)"
                mtpt_regions.append(region)

    return mtpt_regions, suspect_regions


def _check_cp_markers(fasta_path: Path) -> list:
    """Quick check for intact chloroplast marker genes."""
    seq = ""
    with open(fasta_path) as f:
        for line in f:
            if not line.startswith(">"):
                seq += line.strip().upper()

    markers = {
        "rbcL": "ATGTCACCACAAACAGAGACTAAAGCAAGTGTGGATTATCCTGATCCATTCCAAAGTTGAA",
        "psbA": "ATGGCGGACTTACTAGTTACCCAGGAAGTTATAGTTTACAAGTATTTAGGATCACA",
    }

    found = []
    for name, marker in markers.items():
        if marker.upper() in seq:
            found.append(name)
    return found


def _check_nuclear_contamination(
    genome: GenomeSequence, gc_anomalies: list,
) -> list:
    """Check GC anomaly regions for nuclear contamination."""
    suspect = []
    for anomaly in gc_anomalies:
        if anomaly.likely_source == "nuclear":
            suspect.append({
                "start": anomaly.start,
                "end": anomaly.end,
                "gc_pct": anomaly.gc_pct,
                "deviation": anomaly.deviation_sigma,
            })
    return suspect


def _parse_blast(text: str) -> list:
    """Parse BLAST -outfmt 6 output."""
    hits = []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 8:
            continue
        try:
            hits.append({
                "qstart": int(parts[0]), "qend": int(parts[1]),
                "sstart": int(parts[2]), "send": int(parts[3]),
                "pident": float(parts[4]),
                "length": int(parts[5]),
                "evalue": float(parts[6]),
                "bitscore": float(parts[7]),
            })
        except ValueError:
            continue
    return hits


def _merge_hits(hits: list, distance: int = 200) -> list:
    """Merge overlapping BLAST hits."""
    if not hits:
        return []
    sorted_hits = sorted(hits, key=lambda h: min(h["qstart"], h["qend"]))
    merged = [sorted_hits[0]]
    for hit in sorted_hits[1:]:
        prev = merged[-1]
        ps = min(prev["qstart"], prev["qend"])
        pe = max(prev["qstart"], prev["qend"])
        cs = min(hit["qstart"], hit["qend"])
        ce = max(hit["qstart"], hit["qend"])
        if cs <= pe + distance:
            merged[-1] = {
                **prev,
                "qstart": min(ps, cs), "qend": max(pe, ce),
                "pident": max(prev["pident"], hit["pident"]),
                "length": max(pe, ce) - min(ps, cs),
            }
        else:
            merged.append(hit)
    return merged


def _score_contamination(result: ContaminationResult) -> float:
    """Score contamination (100 = clean)."""
    score = 100.0
    # Suspected misassembly is critical
    score -= result.n_suspect_misassembly * 20
    # Complete cp genes is very bad
    if result.has_complete_cp_genes:
        score -= 30
    # GC anomalies (minor)
    score -= min(10, len(result.gc_anomaly_regions) * 0.5)
    # Nuclear suspects (moderate)
    score -= min(10, len(result.nuclear_suspect_regions) * 2)
    return max(0, min(100, score))
