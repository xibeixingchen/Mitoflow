"""QC engine — orchestrates all quality checks.

Five-dimensional assessment:
  1. Completeness  (gene space)
  2. Contiguity    (assembly continuity)
  3. Correctness   (base/structural accuracy)
  4. Contamination (cp/nuclear contamination)
  5. Structure     (repeat consistency, topology)

Usage:
    engine = QCEngine(db_manager)
    result = engine.run(genome, fasta_path, cp_fasta, bam_path)
    print(result.score.summary())
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models.genome import GenomeSequence
from ..db.manager import DBManager

from .completeness import GeneCompletenessResult, assess_gene_completeness
from .contiguity import ContiguityResult, assess_contiguity
from .correctness import CorrectnessResult, assess_correctness
from .contamination import ContaminationResult, detect_contamination
from .structure import StructureResult, assess_structure
from .scorer import QCScore, calculate_overall_score, write_qc_report

logger = logging.getLogger(__name__)


@dataclass
class QCResult:
    """Complete QC result with five dimensions."""
    completeness: GeneCompletenessResult = field(default_factory=GeneCompletenessResult)
    contiguity: ContiguityResult = field(default_factory=ContiguityResult)
    correctness: CorrectnessResult = field(default_factory=CorrectnessResult)
    contamination: ContaminationResult = field(default_factory=ContaminationResult)
    structure: StructureResult = field(default_factory=StructureResult)
    score: QCScore = field(default_factory=QCScore)
    output_files: dict = field(default_factory=dict)

    def summary(self) -> str:
        return self.score.summary()

    @property
    def passed(self) -> bool:
        return self.score.annotation_ready


class QCEngine:
    """Run five-dimensional QC on an assembled mitochondrial genome."""

    def __init__(self, db_manager: Optional[DBManager] = None):
        self.db_manager = db_manager

    def run(
        self,
        genome: GenomeSequence,
        fasta_path: Path,
        cp_fasta: Optional[Path] = None,
        bam_path: Optional[Path] = None,
        reads_sr: Optional[list] = None,
        reads_lr: Optional[str] = None,
        gfa_path: Optional[Path] = None,
        ref_protein: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        name: str = "MitoFlow",
    ) -> QCResult:
        """Run all QC checks.

        Args:
            genome: GenomeSequence object.
            fasta_path: Path to assembly FASTA.
            cp_fasta: Chloroplast genome FASTA (enables MTPT analysis).
            bam_path: Pre-aligned BAM file (enables coverage analysis).
            reads_sr: Short read files [R1, R2].
            reads_lr: Long read file.
            gfa_path: Assembly graph GFA file.
            ref_protein: Reference protein FASTA for miniprot.
            output_dir: Where to write reports.
            name: Project name.

        Returns:
            QCResult with all five dimensions + overall score.
        """
        result = QCResult()

        # Determine HMM database path
        hmm_db = None
        if self.db_manager:
            hmm_db = self.db_manager.combined_hmm

        # Dimension 1: Completeness
        logger.info("Assessing gene completeness...")
        result.completeness = assess_gene_completeness(
            genome=genome,
            fasta_path=fasta_path,
            hmm_db=hmm_db,
            ref_protein=ref_protein,
        )

        # Dimension 2: Contiguity
        logger.info("Assessing contiguity...")
        result.contiguity = assess_contiguity(
            genome=genome,
            fasta_path=fasta_path,
        )

        # Dimension 3: Correctness
        logger.info("Assessing correctness...")
        result.correctness = assess_correctness(
            fasta_path=fasta_path,
            genome=genome,
            bam_path=bam_path,
            reads_sr=reads_sr,
            reads_lr=reads_lr,
            gfa_path=gfa_path,
        )

        # Dimension 4: Contamination
        logger.info("Detecting contamination...")
        result.contamination = detect_contamination(
            genome=genome,
            fasta_path=fasta_path,
            cp_fasta=cp_fasta,
        )

        # Dimension 5: Structure
        logger.info("Assessing structure...")
        result.structure = assess_structure(
            genome=genome,
            fasta_path=fasta_path,
            gfa_path=gfa_path,
            reads_lr=reads_lr,
        )

        # Overall score
        result.score = calculate_overall_score(
            completeness=result.completeness,
            contiguity=result.contiguity,
            correctness=result.correctness,
            contamination=result.contamination,
            structure=result.structure,
        )

        # Write reports if output_dir provided
        if output_dir:
            result.output_files = write_qc_report(
                score=result.score,
                completeness=result.completeness,
                contiguity=result.contiguity,
                correctness=result.correctness,
                contamination=result.contamination,
                structure=result.structure,
                output_dir=output_dir,
                name=name,
            )

        return result
