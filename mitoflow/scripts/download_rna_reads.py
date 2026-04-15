#!/usr/bin/env python3
"""Download RNA-seq reads from SRA for high B/C error species."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/rna_seq/fastq")
STATE_FILE = Path("data/rna_seq/download_state.json")
SPECIES_LIST = Path("data/gold_standard/species_list.csv")

# Target species from Phase 3 high B/C error analysis
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


def load_species_srrs(target_species: list[str] | None = None) -> dict[str, list[str]]:
    """Load SRR accessions from species_list.csv."""
    df = pd.read_csv(SPECIES_LIST)
    mapping: dict[str, list[str]] = {}

    targets = {s.lower().strip() for s in (target_species or DEFAULT_TARGET_SPECIES)}

    for _, row in df.iterrows():
        species = str(row["species"]).strip()
        if species.lower() not in targets:
            continue
        srr_field = str(row.get("sra", "")).strip()
        if not srr_field or srr_field.lower() in ("nan", "none", ""):
            continue
        srrs = [s.strip() for s in srr_field.replace(";", ",").split(",") if s.strip()]
        mapping[species] = srrs

    return mapping


def check_tools() -> tuple[str, str, str | None]:
    """Verify required SRA toolkit binaries are available."""
    prefetch = shutil.which("prefetch")
    fasterq_dump = shutil.which("fasterq-dump")
    pigz = shutil.which("pigz")

    if not prefetch:
        logger.error("prefetch not found in PATH. Install sratoolkit.")
        sys.exit(1)
    if not fasterq_dump:
        logger.error("fasterq-dump not found in PATH. Install sratoolkit.")
        sys.exit(1)

    return prefetch, fasterq_dump, pigz


def download_srr(srr: str, prefetch: str, fasterq_dump: str, pigz: str | None) -> dict:
    """Download a single SRR run. Returns status dict."""
    result = {"srr": srr, "status": "pending", "fastq": [], "error": ""}

    out_dir = OUTPUT_DIR / srr
    out_dir.mkdir(parents=True, exist_ok=True)

    # Check if already done
    done_marker = out_dir / ".done"
    if done_marker.exists():
        result["status"] = "skipped"
        result["fastq"] = [str(p) for p in sorted(out_dir.glob("*.fastq.gz"))]
        return result

    logger.info(f"Downloading {srr} ...")

    # Prefetch (download .sra file; large runs may take >10 min)
    try:
        subprocess.run(
            [prefetch, "-O", str(out_dir), srr],
            capture_output=True,
            text=True,
            timeout=3600,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        result["status"] = "failed"
        result["error"] = f"prefetch failed: {e.stderr or e.stdout}"
        logger.error(result["error"])
        return result
    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["error"] = "prefetch timeout"
        logger.error(result["error"])
        return result

    # fasterq-dump (can be very slow for large RNA-seq runs)
    sra_file = out_dir / f"{srr}.sra"
    if not sra_file.exists():
        # prefetch may create a subdirectory
        sra_file = out_dir / srr / f"{srr}.sra"

    try:
        cmd = [
            fasterq_dump,
            "--outdir", str(out_dir),
            "--split-files",
            "--threads", "4",
            srr,
        ]
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        result["status"] = "failed"
        result["error"] = f"fasterq-dump failed: {e.stderr or e.stdout}"
        logger.error(result["error"])
        return result
    except subprocess.TimeoutExpired:
        result["status"] = "failed"
        result["error"] = "fasterq-dump timeout"
        logger.error(result["error"])
        return result

    # Compress with pigz or gzip
    fastq_files = sorted(out_dir.glob("*.fastq"))
    if not fastq_files:
        result["status"] = "failed"
        result["error"] = "no FASTQ files produced"
        logger.error(result["error"])
        return result

    for fq in fastq_files:
        gz = fq.with_suffix(fq.suffix + ".gz")
        try:
            if pigz:
                subprocess.run(
                    [pigz, "-p", "4", "-f", str(fq)],
                    capture_output=True,
                    timeout=600,
                    check=True,
                )
            else:
                subprocess.run(
                    ["gzip", "-f", str(fq)],
                    capture_output=True,
                    timeout=1200,
                    check=True,
                )
            result["fastq"].append(str(gz))
        except subprocess.CalledProcessError as e:
            logger.warning(f"Compression failed for {fq}: {e}")
            result["fastq"].append(str(fq))  # keep uncompressed

    result["status"] = "success"
    done_marker.write_text("done\n")
    logger.info(f"{srr} completed -> {', '.join(result['fastq'])}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Download RNA-seq reads for validation")
    parser.add_argument("--species", nargs="+", help="Subset of species to download")
    parser.add_argument("--resume", action="store_true", help="Skip already downloaded runs")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be downloaded")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    prefetch, fasterq_dump, pigz = check_tools()
    species_srrs = load_species_srrs(args.species)

    if not species_srrs:
        logger.error("No SRR accessions found for target species.")
        sys.exit(1)

    logger.info(f"Target species: {len(species_srrs)}")
    for sp, srrs in species_srrs.items():
        logger.info(f"  {sp}: {', '.join(srrs)}")

    if args.dry_run:
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load previous state if resuming
    state: dict = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

    # Auto-recover: any SRR directory with existing FASTQ files is treated as completed
    for srr_dir in OUTPUT_DIR.iterdir():
        if srr_dir.is_dir():
            fastqs = list(srr_dir.glob("*.fastq.gz")) + list(srr_dir.glob("*.fastq"))
            if fastqs:
                state.setdefault("completed", []).append(srr_dir.name)
    # Deduplicate
    state["completed"] = list(dict.fromkeys(state.get("completed", [])))

    total = sum(len(v) for v in species_srrs.values())
    completed = 0
    failed = 0
    skipped = 0

    for species, srrs in species_srrs.items():
        for srr in srrs:
            if args.resume and srr in state.get("completed", []):
                logger.info(f"Skipping {srr} (already in state)")
                skipped += 1
                continue

            result = download_srr(srr, prefetch, fasterq_dump, pigz)

            if result["status"] == "success":
                completed += 1
                state.setdefault("completed", []).append(srr)
            elif result["status"] == "skipped":
                skipped += 1
                state.setdefault("completed", []).append(srr)
            else:
                failed += 1
                state.setdefault("failed", {})[srr] = result.get("error", "unknown")

            # Save state after each run
            state["total"] = total
            state["completed_count"] = completed
            state["failed_count"] = failed
            state["skipped_count"] = skipped
            STATE_FILE.write_text(json.dumps(state, indent=2))

    logger.info("=" * 40)
    logger.info(f"Total: {total} | Completed: {completed} | Skipped: {skipped} | Failed: {failed}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
