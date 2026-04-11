"""Output directory layout manager."""

from __future__ import annotations
from pathlib import Path


class OutputManager:
    """Manage output directory structure for annotation results.

    Directories are created on demand (lazy), not upfront.
    Only ``root`` is created by ``setup()``; sub-directories are
    auto-created the first time a property that references them is used.
    """

    def __init__(self, output_dir: Path, project_name: str):
        self.root = Path(output_dir)
        self.project_name = project_name

    def setup(self) -> None:
        """Create the root output directory."""
        self.root.mkdir(parents=True, exist_ok=True)

    def _ensure(self, path: Path) -> Path:
        """Ensure a directory exists and return it."""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def gff_dir(self) -> Path:
        return self._ensure(self.root / "gff")

    @property
    def gbk_dir(self) -> Path:
        return self._ensure(self.root / "genbank")

    @property
    def fasta_dir(self) -> Path:
        return self._ensure(self.root / "fasta")

    @property
    def report_dir(self) -> Path:
        return self._ensure(self.root / "report")

    @property
    def tmp_dir(self) -> Path:
        return self._ensure(self.root / "tmp")

    @property
    def gff_path(self) -> Path:
        return self.gff_dir / f"{self.project_name}.gff"

    @property
    def gbk_path(self) -> Path:
        return self.gbk_dir / f"{self.project_name}.gbk"

    @property
    def cds_fasta(self) -> Path:
        return self.fasta_dir / f"{self.project_name}.CDS.fasta"

    @property
    def protein_fasta(self) -> Path:
        return self.fasta_dir / f"{self.project_name}.Protein.fasta"

    @property
    def trna_fasta(self) -> Path:
        return self.fasta_dir / f"{self.project_name}.tRNA.fasta"

    @property
    def rrna_fasta(self) -> Path:
        return self.fasta_dir / f"{self.project_name}.rRNA.fasta"

    @property
    def intron_fasta(self) -> Path:
        return self.fasta_dir / f"{self.project_name}.intron.fasta"

    @property
    def gene_fasta(self) -> Path:
        return self.fasta_dir / f"{self.project_name}.Gene.fasta"

    @property
    def report_html(self) -> Path:
        return self.report_dir / f"{self.project_name}_report.html"

    @property
    def report_tsv(self) -> Path:
        return self.report_dir / f"{self.project_name}_annotation.tsv"

    def cleanup_tmp(self) -> None:
        """Remove temporary files."""
        import shutil
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
