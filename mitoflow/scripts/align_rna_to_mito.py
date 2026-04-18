#!/usr/bin/env python3
"""Align RNA-seq reads to mitochondrial genomes and extract splice junctions."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

FASTQ_DIR = Path("data/rna_seq/fastq")
BAM_DIR = Path("data/rna_seq/bam")
JUNC_DIR = Path("data/rna_seq/junctions")
STATE_FILE = Path("data/rna_seq/align_state.json")
GENOME_DIR = Path("data/gold_standard/fasta")


def check_tools() -> tuple[str, str, str]:
    """Verify required binaries."""
    minimap2 = shutil.which("minimap2")
    samtools = shutil.which("samtools")
    if not minimap2:
        logger.error("minimap2 not found in PATH.")
        sys.exit(1)
    if not samtools:
        logger.error("samtools not found in PATH.")
        sys.exit(1)
    return minimap2, samtools


def find_fastq_files(srr: str) -> list[Path]:
    """Find FASTQ files for an SRR run."""
    out_dir = FASTQ_DIR / srr
    fqs = [
        p
        for p in sorted(out_dir.glob("*.fastq.gz")) + sorted(out_dir.glob("*.fastq"))
        if p.stat().st_size > 0
    ]
    return fqs


def align_and_process(
    species_name: str,
    srr: str,
    minimap2: str,
    samtools: str,
    threads: int = 4,
) -> dict:
    """Align RNA-seq reads to the mitochondrial genome and extract junctions."""
    result = {
        "srr": srr,
        "species": species_name,
        "status": "pending",
        "bam": "",
        "junctions": "",
        "mapped_reads": 0,
        "error": "",
    }

    genome_fa = GENOME_DIR / f"{species_name}.fasta"
    if not genome_fa.exists():
        # Fallback: search for any fasta matching the species base name
        base = species_name.replace("_", "*").replace("'", "*")
        candidates = sorted(GENOME_DIR.glob(f"*{base}*.fasta"))
        if not candidates:
            # Try looser match
            candidates = sorted(GENOME_DIR.glob("*.fasta"))
            for c in candidates:
                if species_name.replace("_", " ").lower() in c.stem.lower():
                    genome_fa = c
                    break
        else:
            genome_fa = candidates[0]

    if not genome_fa.exists():
        result["status"] = "failed"
        result["error"] = f"Genome not found for {species_name}"
        logger.error(result["error"])
        return result

    fastqs = find_fastq_files(srr)
    if not fastqs:
        result["status"] = "failed"
        result["error"] = f"No FASTQ files found for {srr}"
        logger.error(result["error"])
        return result

    BAM_DIR.mkdir(parents=True, exist_ok=True)
    JUNC_DIR.mkdir(parents=True, exist_ok=True)

    bam_path = BAM_DIR / f"{species_name}_{srr}.sorted.bam"
    junc_path = JUNC_DIR / f"{species_name}_{srr}.junctions.bed"
    done_marker = bam_path.with_suffix(bam_path.suffix + ".done")

    if done_marker.exists():
        result["status"] = "skipped"
        result["bam"] = str(bam_path)
        result["junctions"] = str(junc_path) if junc_path.exists() else ""
        logger.info(f"Skipping {srr} (already aligned)")
        return result

    logger.info(f"Aligning {srr} ({species_name}) ...")

    # minimap2 -ax splice:sr for spliced short RNA-seq reads
    # Pipe to samtools sort
    try:
        minimap_cmd = [
            minimap2,
            "-ax", "splice:sr",
            "-t", str(threads),
            str(genome_fa),
        ] + [str(fq) for fq in fastqs]

        with open(bam_path, "wb") as bam_fh:
            minimap_proc = subprocess.Popen(
                minimap_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            sort_proc = subprocess.Popen(
                [samtools, "sort", "-@", str(threads), "-o", "-", "-"],
                stdin=minimap_proc.stdout,
                stdout=bam_fh,
                stderr=subprocess.PIPE,
            )
            minimap_proc.stdout.close()
            sort_stdout, sort_stderr = sort_proc.communicate(timeout=7200)
            minimap_stderr = minimap_proc.stderr.read().decode("utf-8", errors="ignore")
            minimap_proc.wait(timeout=60)

            if minimap_proc.returncode != 0:
                raise subprocess.CalledProcessError(
                    minimap_proc.returncode, minimap_cmd, output=minimap_stderr
                )
            if sort_proc.returncode != 0:
                raise subprocess.CalledProcessError(
                    sort_proc.returncode, [samtools, "sort"], output=sort_stderr.decode("utf-8", errors="ignore")
                )
    except subprocess.CalledProcessError as e:
        result["status"] = "failed"
        result["error"] = f"Alignment failed: {e.output or e.stderr}"
        logger.error(result["error"])
        return result
    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["error"] = "Alignment timeout"
        logger.error(result["error"])
        return result

    # Index BAM
    try:
        subprocess.run(
            [samtools, "index", str(bam_path)],
            capture_output=True,
            timeout=300,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.warning(f"BAM index failed: {e}")

    # Count mapped reads (primary alignments, MAPQ >= 1)
    try:
        count_proc = subprocess.run(
            [samtools, "view", "-c", "-F", "260", "-q", "1", str(bam_path)],
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
        result["mapped_reads"] = int(count_proc.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.warning(f"Could not count mapped reads: {e}")

    # Extract splice junctions from CIGAR strings
    # Look for N > 10bp (splice intron)
    logger.info(f"Extracting junctions for {srr} ...")
    try:
        junc_lines = _extract_junctions_from_bam(str(bam_path), samtools, species_name)
        junc_path.write_text("\n".join(junc_lines) + "\n")
        result["junctions"] = str(junc_path)
    except Exception as e:
        logger.warning(f"Junction extraction failed: {e}")
        result["junctions"] = ""

    result["status"] = "success"
    result["bam"] = str(bam_path)
    done_marker.write_text("done\n")
    logger.info(
        f"{srr} aligned: {bam_path} ({result['mapped_reads']:,} mapped reads), "
        f"junctions: {junc_path}"
    )
    return result


def _extract_junctions_from_bam(bam_path: str, samtools: str, species_name: str) -> list[str]:
    """Parse BAM and extract splice junctions into a simple BED-like format.

    BED columns:
    chrom start end strand n_reads left_motif right_motif
    """
    # Use samtools view to get minimal fields: flag, ref, pos, cigar, tlen, seq
    cmd = [samtools, "view", "-F", "260", bam_path]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, check=True)

    junc_counts: dict[tuple[str, int, int, str], int] = {}
    for line in proc.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        flag = int(parts[1])
        ref = parts[2]
        pos = int(parts[3])
        cigar = parts[5]

        strand = "-" if (flag & 16) else "+"

        # Parse CIGAR for N (skipped region = intron)
        import re
        cig_iter = re.finditer(r"(\d+)([MIDNSHP=X])", cigar)
        cursor = pos
        for m in cig_iter:
            length = int(m.group(1))
            op = m.group(2)
            if op in ("M", "=", "X", "D"):
                cursor += length
            elif op == "N":
                if length > 10:
                    junc_key = (ref, cursor, cursor + length - 1, strand)
                    junc_counts[junc_key] = junc_counts.get(junc_key, 0) + 1
                cursor += length
            # I, S, H, P do not advance cursor on reference

    lines = []
    for (ref, start, end, strand), count in sorted(junc_counts.items()):
        # simple BED: chrom start end name score strand
        lines.append(
            f"{ref}\t{start - 1}\t{end}\t.\t{count}\t{strand}\t.\t."
        )
    return lines


def load_download_state() -> dict:
    """Load download state to know which SRRs are ready."""
    download_state = Path("data/rna_seq/download_state.json")
    state: dict = {}
    if download_state.exists():
        state = json.loads(download_state.read_text())
    # Also auto-detect any SRR directory with existing FASTQ files
    for srr_dir in FASTQ_DIR.iterdir():
        if srr_dir.is_dir():
            fastqs = list(srr_dir.glob("*.fastq.gz")) + list(srr_dir.glob("*.fastq"))
            if fastqs:
                state.setdefault("completed", []).append(srr_dir.name)
    state["completed"] = list(dict.fromkeys(state.get("completed", [])))
    return state


def main():
    parser = argparse.ArgumentParser(description="Align RNA-seq to mitochondrial genomes")
    parser.add_argument("--threads", "-t", type=int, default=4, help="Number of threads")
    parser.add_argument("--species", help="Single species name to align")
    parser.add_argument("--resume", action="store_true", help="Skip already aligned runs")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    minimap2, samtools = check_tools()
    dl_state = load_download_state()
    completed_srrs = set(dl_state.get("completed", []))

    # Species -> SRR mapping (same as download script)
    import pandas as pd
    SPECIES_LIST = Path("data/gold_standard/species_list.csv")
    DEFAULT_TARGET_SPECIES = [
        "Camellia sinensis var. assamica",
        "Nymphaea hybrid cultivar 'Joey Tomocik'",
        "Liriodendron tulipifera",
        "Eucommia ulmoides",
        "Pontederia crassipes",
        "Selenicereus monacanthus",
        "Glycine max",
        "Capsicum annuum cultivar Jeju",
    ]
    df = pd.read_csv(SPECIES_LIST)
    targets = {s.lower().strip() for s in ([args.species] if args.species else DEFAULT_TARGET_SPECIES)}
    species_srrs: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        species = str(row["species"]).strip()
        if species.lower() not in targets:
            continue
        srr_field = str(row.get("sra", "")).strip()
        if not srr_field or srr_field.lower() in ("nan", "none", ""):
            continue
        srrs = [s.strip() for s in srr_field.replace(";", ",").split(",") if s.strip()]
        species_srrs[species] = srrs

    total = 0
    success = 0
    failed = 0
    skipped = 0

    state: dict = {"completed": [], "failed": {}}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

    for species, srrs in species_srrs.items():
        species_safe = species.replace(" ", "_").replace(".", "").replace("'", "")
        for srr in srrs:
            total += 1
            if srr not in completed_srrs:
                logger.warning(f"{srr} not yet downloaded, skipping alignment")
                failed += 1
                continue

            if args.resume and srr in state.get("completed", []):
                logger.info(f"Skipping {srr} (already aligned)")
                skipped += 1
                continue

            result = align_and_process(species_safe, srr, minimap2, samtools, args.threads)

            if result["status"] == "success":
                success += 1
                state.setdefault("completed", []).append(srr)
            elif result["status"] == "skipped":
                skipped += 1
            else:
                failed += 1
                state.setdefault("failed", {})[srr] = result.get("error", "unknown")

            state["total"] = total
            state["success"] = success
            state["failed_count"] = failed
            state["skipped_count"] = skipped
            STATE_FILE.write_text(json.dumps(state, indent=2))

    logger.info("=" * 40)
    logger.info(f"Total: {total} | Success: {success} | Skipped: {skipped} | Failed: {failed}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
