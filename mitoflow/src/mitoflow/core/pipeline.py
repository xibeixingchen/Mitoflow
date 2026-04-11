"""Annotation pipeline orchestrator.

Wires all modules together:
  1. Load FASTA
  2. Annotate PCG (pyhmmer)
  3. Annotate tRNA (tRNAscan-SE + ARAGORN)
  4. Annotate rRNA (Barrnap)
  5. Boundary correction
  6. CDS validation
  7. Write GFF3 + GenBank
  8. Extract sequences
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..models.genome import GenomeSequence
from ..models.gene import GeneAnnotation
from ..models.feature import tRNAAnnotation, rRNAAnnotation
from .input import load_fasta, validate_fasta
from .output import OutputManager
from ..annotate.pcg import annotate_pcg, PCGConfig
from ..annotate.trna import annotate_trna
from ..annotate.rrna import annotate_rrna
from ..annotate.boundary import correct_boundaries
from ..annotate.cds_check import validate_cds, CDSValidationResult
from ..annotate.gff_handler import write_gff3, write_genbank
from ..extract.sequences import extract_all
from ..db.manager import DBManager
from ..qc.qc_engine import QCEngine, QCResult
from ..mtpt.detector import detect_mtpt, annotate_trna_origin, MTPTResult

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class PipelineConfig:
    db_path: Optional[Path] = None
    threads: int = 4
    evalue: float = 1e-5
    skip_trna: bool = False
    skip_rrna: bool = False
    skip_qc: bool = False
    skip_mtpt: bool = False
    transl_table: int = 1  # Standard genetic code (Table 1)


@dataclass
class PipelineResult:
    genome: GenomeSequence
    annotations: list[GeneAnnotation] = field(default_factory=list)
    trna_annotations: list[tRNAAnnotation] = field(default_factory=list)
    rrna_annotations: list[rRNAAnnotation] = field(default_factory=list)
    cds_validation: Optional[CDSValidationResult] = None
    qc_result: Optional[QCResult] = None
    mtpt_result: Optional[MTPTResult] = None
    warnings: list[str] = field(default_factory=list)
    output_dir: Optional[Path] = None

    def summary(self) -> str:
        pcg = sum(1 for a in self.annotations if a.gene_type == "CDS")
        trna = len(self.trna_annotations)
        rrna = len(self.rrna_annotations)
        total = pcg + trna + rrna
        gc = self.genome.gc_content
        return (
            f"Genome: {self.genome.length:,} bp, GC={gc:.1f}% | "
            f"PCG: {pcg} | tRNA: {trna} | rRNA: {rrna} | Total: {total}"
        )


class AnnotationPipeline:
    """Main annotation pipeline."""

    def __init__(self, db_path: Optional[Path] = None, threads: int = 4):
        self.config = PipelineConfig(db_path=db_path, threads=threads)
        self.db_manager = DBManager(db_path)

    def run(
        self,
        fasta_path: Path,
        output_dir: Path,
        name: str,
        skip_trna: bool = False,
        skip_rrna: bool = False,
        skip_qc: bool = False,
        skip_mtpt: bool = True,
        cp_fasta: Optional[Path] = None,
        bam_path: Optional[Path] = None,
    ) -> PipelineResult:
        """Run the full annotation pipeline."""
        self.config.skip_trna = skip_trna
        self.config.skip_rrna = skip_rrna
        self.config.skip_qc = skip_qc
        self.config.skip_mtpt = skip_mtpt

        out = OutputManager(output_dir, name)
        out.setup()

        # Step 1: Load input
        console.print("[bold blue]Step 1/8[/] Loading input FASTA...")
        genome = load_fasta(fasta_path)
        warnings = validate_fasta(genome)
        for w in warnings:
            console.print(f"  [yellow]warning:[/] {w}")

        console.print(f"  Genome: {genome.length:,} bp, GC={genome.gc_content:.1f}%")

        # Verify database
        db_issues = self.db_manager.verify()
        if db_issues:
            for issue in db_issues:
                console.print(f"  [red]DB issue:[/] {issue}")
            return PipelineResult(genome=genome, warnings=db_issues, output_dir=out.root)

        # Step 2: Annotate PCG
        console.print("[bold blue]Step 2/8[/] Annotating protein-coding genes...")
        pcg_config = PCGConfig(evalue=self.config.evalue, threads=self.config.threads)
        annotations = annotate_pcg(genome, self.db_manager, pcg_config)
        console.print(f"  Found {len(annotations)} protein-coding genes")

        # Step 3: Annotate tRNA
        trna_annotations = []
        if not skip_trna:
            console.print("[bold blue]Step 3/8[/] Annotating tRNA genes...")
            trna_annotations = annotate_trna(fasta_path, out.tmp_dir, self.config.threads, db_manager=self.db_manager)
            console.print(f"  Found {len(trna_annotations)} tRNA genes")
        else:
            console.print("[dim]Step 3/8[/] tRNA annotation skipped")

        # Step 4: Annotate rRNA
        rrna_annotations = []
        if not skip_rrna:
            console.print("[bold blue]Step 4/8[/] Annotating rRNA genes...")
            rrna_annotations = annotate_rrna(fasta_path, out.tmp_dir, db_manager=self.db_manager)
            console.print(f"  Found {len(rrna_annotations)} rRNA genes")
        else:
            console.print("[dim]Step 4/8[/] rRNA annotation skipped")

        # Step 5: Boundary correction
        console.print("[bold blue]Step 5/8[/] Correcting gene boundaries...")
        annotations = correct_boundaries(annotations, genome, self.db_manager)

        # Step 6: CDS validation
        console.print("[bold blue]Step 6/8[/] Validating CDS...")
        cds_result = validate_cds(annotations, genome, self.db_manager)
        console.print(f"  {cds_result.summary()}")
        if cds_result.missing_core:
            console.print(f"  [yellow]Missing core genes:[/] {', '.join(cds_result.missing_core)}")

        # Step 7: Write output files
        console.print("[bold blue]Step 7/8[/] Writing output files...")
        write_gff3(annotations, trna_annotations, rrna_annotations, genome, out.gff_path)
        write_genbank(
            annotations, trna_annotations, rrna_annotations,
            genome, out.gbk_path, organism=name,
        )

        # Step 8: Extract sequences
        console.print("[bold blue]Step 8/8[/] Extracting sequences...")
        extract_all(
            annotations, trna_annotations, rrna_annotations,
            genome, out.fasta_dir, name,
        )

        # Step 9: QC (optional)
        qc_result = None
        if not skip_qc:
            console.print("[bold blue]Step 9/10[/] Running quality control (5 dimensions)...")
            qc_engine = QCEngine(db_manager=self.db_manager)
            qc_result = qc_engine.run(
                genome=genome,
                fasta_path=fasta_path,
                cp_fasta=cp_fasta,
                bam_path=bam_path,
                output_dir=out.report_dir,
                name=name,
            )
            score = qc_result.score
            console.print(
                f"  QC Score: {score.overall_score:.0f}/100 "
                f"(Grade: {score.overall_grade}) "
                f"{'PASS' if score.annotation_ready else 'FAIL'}"
            )
            if score.critical_warnings:
                for w in score.critical_warnings:
                    console.print(f"  [red]CRITICAL:[/] {w}")
            if score.warnings:
                for w in score.warnings:
                    console.print(f"  [yellow]Warning:[/] {w}")
        else:
            console.print("[dim]Step 9/10[/] QC skipped")

        # Step 10: MTPT detection (optional, requires cp genome)
        mtpt_result = None
        if not skip_mtpt and cp_fasta:
            console.print("[bold blue]Step 10/10[/] Detecting MTPT regions...")
            mtpt_result = detect_mtpt(
                mito_fasta=fasta_path, cp_fasta=cp_fasta,
                genome=genome, threads=self.config.threads,
            )
            console.print(
                f"  Found {len(mtpt_result.regions)} MTPT regions "
                f"({mtpt_result.total_mtpt_bp:,} bp, {mtpt_result.mtpt_pct:.2f}%)"
            )
            # Annotate tRNA origin
            if trna_annotations:
                trna_annotations = annotate_trna_origin(
                    trna_annotations, mtpt_result.regions, genome,
                )
                cp_trna_count = sum(1 for t in trna_annotations if t.is_cp_derived)
                if cp_trna_count:
                    console.print(f"  {cp_trna_count} cp-derived tRNAs identified")

            # Write MTPT report
            report_dir = out.report_dir
            report_dir.mkdir(parents=True, exist_ok=True)
            mtpt_path = report_dir / f"{name}_mtpt.txt"
            mtpt_path.write_text(mtpt_result.summary())
        else:
            console.print("[dim]Step 10/10[/] MTPT detection skipped")
            # QC reports already written by qc_engine.run() with output_dir

        # Cleanup
        out.cleanup_tmp()

        # Final summary
        result = PipelineResult(
            genome=genome,
            annotations=annotations,
            trna_annotations=trna_annotations,
            rrna_annotations=rrna_annotations,
            cds_validation=cds_result,
            qc_result=qc_result,
            mtpt_result=mtpt_result,
            warnings=warnings,
            output_dir=out.root,
        )
        console.print(f"\n[bold green]Done![/] {result.summary()}")
        console.print(f"Output: {out.root}")

        return result
