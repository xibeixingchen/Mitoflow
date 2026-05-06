"""Shared configuration constants for the MitoFlow web backend."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

UPLOAD_DIR = Path(os.getenv("MITOFLOW_UPLOAD_DIR", PROJECT_ROOT / "mitoflow_uploads"))
RESULTS_DIR = Path(os.getenv("MITOFLOW_RESULTS_DIR", PROJECT_ROOT / "mitoflow_results"))
WORKSPACE_ROOT = Path(os.getenv("MITOFLOW_WORKSPACE", PROJECT_ROOT / "mitoflow_workspace"))

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_UPLOAD_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
ALLOWED_EXTENSIONS = {".fasta", ".fa", ".fas", ".fna"}
ALLOWED_EXTENSIONS_UPLOAD = {
    ".fasta", ".fa", ".fas", ".fna", ".fq", ".fastq", ".fq.gz", ".fastq.gz",
    ".gb", ".gbk", ".gbff", ".gff", ".gff3", ".gtf",
    ".vcf", ".bam", ".bai", ".sam",
    ".csv", ".tsv", ".txt",
    ".nwk", ".treefile", ".tre", ".phylip", ".phy",
    ".zip", ".tar.gz", ".tar.bz2",
    ".png", ".jpg", ".svg", ".pdf",
}

UPLOAD_DIR = UPLOAD_DIR.resolve()
RESULTS_DIR = RESULTS_DIR.resolve()
WORKSPACE_ROOT = WORKSPACE_ROOT.resolve()
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
RESULTS_DIR.mkdir(exist_ok=True, parents=True)
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


def safe_path(base: Path, rel: str) -> Path:
    """Resolve a relative path under base, rejecting path traversal."""
    target = (base / rel).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Path traversal denied")
    return target
