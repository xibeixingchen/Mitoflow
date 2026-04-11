"""Download CMS reference protein sequences from NCBI.

Usage:
    python -m mitoflow.data.cms.download

Downloads sequences from NCBI Entrez using accessions in cms_reference.json,
builds cms_proteins.fasta and BLAST database for CMS prediction.
"""

from __future__ import annotations
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent
REF_JSON = DATA_DIR / "cms_reference.json"
OUTPUT_FA = DATA_DIR / "cms_proteins.fasta"


def download_cms_sequences(email: str = "user@example.com") -> Path:
    """Download CMS protein sequences from NCBI Entrez.

    Args:
        email: Email for NCBI Entrez (required by their policy).

    Returns:
        Path to the downloaded FASTA file.
    """
    try:
        from Bio import Entrez, SeqIO
    except ImportError:
        raise ImportError("biopython required: pip install biopython")

    Entrez.email = email

    if not REF_JSON.exists():
        raise FileNotFoundError(f"Reference JSON not found: {REF_JSON}")

    with open(REF_JSON) as f:
        references = json.load(f)

    accessions = [r["accession"] for r in references if r.get("accession")]
    logger.info(f"Downloading {len(accessions)} CMS protein sequences from NCBI...")

    records = []
    failed = []

    for i, acc in enumerate(accessions):
        # Find metadata
        meta = next((r for r in references if r.get("accession") == acc), {})
        name = meta.get("name", acc)
        species = meta.get("species", "unknown")
        cms_type = meta.get("cms_type", "unknown")

        logger.info(f"  [{i + 1}/{len(accessions)}] {acc} ({name}, {species}, {cms_type})")

        try:
            handle = Entrez.efetch(
                db="protein", id=acc, rettype="fasta", retmode="text",
            )
            record = next(SeqIO.parse(handle, "fasta"))
            handle.close()

            # Rewrite header with CMS metadata
            record.id = name
            record.description = (
                f"{name} | {species} | {cms_type} | "
                f"accession={acc} | length={len(record.seq)}aa | "
                f"chimera={meta.get('chimera_sources', 'unknown')} | "
                f"evidence={meta.get('evidence', 'unknown')}"
            )
            records.append(record)

        except Exception as e:
            logger.warning(f"    Failed to download {acc}: {e}")
            failed.append(acc)

        # NCBI rate limit: max 3 requests/second
        time.sleep(0.4)

    # Write FASTA
    SeqIO.write(records, str(OUTPUT_FA), "fasta")
    logger.info(f"Wrote {len(records)} sequences to {OUTPUT_FA}")

    if failed:
        logger.warning(f"Failed to download {len(failed)} accessions: {failed}")
        # Write failed list for retry
        failed_path = DATA_DIR / "failed_accessions.txt"
        failed_path.write_text("\n".join(failed))
        logger.info(f"Failed accessions saved to {failed_path}")

    # Build BLAST database
    _build_blast_db(OUTPUT_FA)

    return OUTPUT_FA


def _build_blast_db(fasta_path: Path) -> None:
    """Build BLAST protein database from CMS reference FASTA."""
    makeblastdb = shutil.which("makeblastdb")
    if not makeblastdb:
        logger.warning("makeblastdb not found — skip BLAST DB building")
        return

    db_path = fasta_path.parent / "cms_proteins"
    proc = subprocess.run(
        [makeblastdb, "-in", str(fasta_path), "-dbtype", "prot",
         "-out", str(db_path), "-parse_seqids"],
        capture_output=True, text=True,
    )
    if proc.returncode == 0:
        logger.info(f"BLAST database built: {db_path}")
    else:
        logger.warning(f"makeblastdb failed: {proc.stderr}")


if __name__ == "__main__":
    download_cms_sequences()
