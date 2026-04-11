"""Overall QC scoring and reporting.

Combines all five dimensions into a single score and generates reports.
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .completeness import GeneCompletenessResult
from .contiguity import ContiguityResult
from .correctness import CorrectnessResult
from .contamination import ContaminationResult
from .structure import StructureResult

logger = logging.getLogger(__name__)


@dataclass
class QCScore:
    """Overall QC score combining all five dimensions."""
    # Dimension scores (0-100)
    completeness_score: float = 0.0
    contiguity_score: float = 0.0
    correctness_score: float = 0.0
    contamination_score: float = 0.0
    structure_score: float = 0.0

    # Overall
    overall_score: float = 0.0
    overall_grade: str = "F"

    # Warnings
    critical_warnings: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    # Verdict
    annotation_ready: bool = False

    def summary(self) -> str:
        lines = [
            "=" * 50,
            "MitoFlow QC Report",
            "=" * 50,
            "",
            f"Overall Score: {self.overall_score:.0f}/100  Grade: {self.overall_grade}",
            f"Annotation Ready: {'YES' if self.annotation_ready else 'NO'}",
            "",
            f"  Completeness:   {self.completeness_score:5.0f}/100",
            f"  Contiguity:     {self.contiguity_score:5.0f}/100",
            f"  Correctness:    {self.correctness_score:5.0f}/100",
            f"  Contamination:  {self.contamination_score:5.0f}/100",
            f"  Structure:      {self.structure_score:5.0f}/100",
        ]
        if self.critical_warnings:
            lines.append("")
            lines.append("CRITICAL WARNINGS:")
            for w in self.critical_warnings:
                lines.append(f"  [!] {w}")
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.notes:
            lines.append("")
            lines.append("Notes:")
            for n in self.notes:
                lines.append(f"  * {n}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "scores": {
                "completeness": round(self.completeness_score, 1),
                "contiguity": round(self.contiguity_score, 1),
                "correctness": round(self.correctness_score, 1),
                "contamination": round(self.contamination_score, 1),
                "structure": round(self.structure_score, 1),
                "overall": round(self.overall_score, 1),
                "grade": self.overall_grade,
            },
            "annotation_ready": self.annotation_ready,
            "critical_warnings": self.critical_warnings,
            "warnings": self.warnings,
        }


def calculate_overall_score(
    completeness: GeneCompletenessResult,
    contiguity: ContiguityResult,
    correctness: CorrectnessResult,
    contamination: ContaminationResult,
    structure: StructureResult,
) -> QCScore:
    """Calculate overall QC score from five dimensions.

    Weights:
    - Completeness: 0.35 (most important — missing genes = can't annotate)
    - Correctness:  0.25 (base errors affect gene prediction)
    - Contiguity:   0.15 (fragmented but complete is still annotatable)
    - Contamination:0.15 (leads to false positive annotations)
    - Structure:    0.10 (affects downstream but not annotation)

    Grades:
    - A (90-100): Publication-ready
    - B (75-89):  Good, safe to annotate
    - C (60-74):  Fair, recommend improvement
    - D (40-59):  Poor, reassembly recommended
    - F (<40):    Fail, must reassemble
    """
    score = QCScore(
        completeness_score=completeness.score,
        contiguity_score=contiguity.contiguity_score,
        correctness_score=correctness.correctness_score,
        contamination_score=contamination.contamination_score,
        structure_score=structure.structure_score,
    )

    # Weighted average
    score.overall_score = (
        completeness.score * 0.35 +
        correctness.correctness_score * 0.25 +
        contiguity.contiguity_score * 0.15 +
        contamination.contamination_score * 0.15 +
        structure.structure_score * 0.10
    )

    # Grade
    if score.overall_score >= 90:
        score.overall_grade = "A"
    elif score.overall_score >= 75:
        score.overall_grade = "B"
    elif score.overall_score >= 60:
        score.overall_grade = "C"
    elif score.overall_score >= 40:
        score.overall_grade = "D"
    else:
        score.overall_grade = "F"

    # Critical warnings
    if completeness.essential_missing:
        score.critical_warnings.append(
            f"Essential genes missing: {', '.join(completeness.essential_missing)}"
        )
    if contamination.has_complete_cp_genes:
        score.critical_warnings.append(
            "Complete chloroplast genes detected — possible cp contamination"
        )
    if contiguity.total_length < 100_000:
        score.critical_warnings.append(
            f"Genome too short ({contiguity.total_length:,} bp)"
        )

    # Regular warnings
    if completeness.missing_genes:
        variable = [g for g in completeness.missing_genes
                    if g not in completeness.essential_missing]
        if variable:
            score.warnings.append(
                f"Variable genes missing: {', '.join(variable)}"
            )
    if completeness.fragmented_genes:
        score.warnings.append(
            f"Fragmented genes: {', '.join(completeness.fragmented_genes)}"
        )
    if correctness.coverage.cv > 0.5:
        score.warnings.append(
            f"Coverage uneven (CV={correctness.coverage.cv:.2f})"
        )
    if not structure.repeat_consistency:
        score.warnings.append("Inconsistent repeat copies")
    for w in contiguity.warnings:
        score.warnings.append(w)
    for w in contamination.warnings:
        score.warnings.append(w)
    for w in structure.warnings:
        score.warnings.append(w)

    # Notes
    if completeness.duplicated_genes:
        score.notes.append(
            f"Duplicated genes: {', '.join(completeness.duplicated_genes)} "
            f"(atp6 duplication is common)"
        )

    # Annotation ready
    score.annotation_ready = (
        score.overall_score >= 60 and len(score.critical_warnings) == 0
    )

    return score


def write_qc_report(
    score: QCScore,
    completeness: GeneCompletenessResult,
    contiguity: ContiguityResult,
    correctness: CorrectnessResult,
    contamination: ContaminationResult,
    structure: StructureResult,
    output_dir: Path,
    name: str = "MitoFlow",
) -> dict:
    """Write all QC output files.

    Returns dict of file paths written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {}

    # Text report
    txt_path = output_dir / f"{name}_qc.txt"
    txt_path.write_text(score.summary() + "\n\n" +
                        completeness.summary() + "\n\n" +
                        contiguity.summary() + "\n\n" +
                        correctness.summary() + "\n\n" +
                        contamination.summary() + "\n\n" +
                        structure.summary())
    files["report_txt"] = txt_path

    # JSON scores
    json_path = output_dir / f"{name}_qc_scores.json"
    with open(json_path, "w") as f:
        json.dump(score.to_dict(), f, indent=2)
    files["scores_json"] = json_path

    # TSV summary
    tsv_path = output_dir / f"{name}_qc_summary.tsv"
    with open(tsv_path, "w") as f:
        f.write("dimension\tscore\tweight\n")
        f.write(f"completeness\t{score.completeness_score:.1f}\t0.35\n")
        f.write(f"correctness\t{score.correctness_score:.1f}\t0.25\n")
        f.write(f"contiguity\t{score.contiguity_score:.1f}\t0.15\n")
        f.write(f"contamination\t{score.contamination_score:.1f}\t0.15\n")
        f.write(f"structure\t{score.structure_score:.1f}\t0.10\n")
        f.write(f"overall\t{score.overall_score:.1f}\t-\n")
        f.write(f"grade\t{score.overall_grade}\t-\n")
        f.write(f"annotation_ready\t{score.annotation_ready}\t-\n")
    files["summary_tsv"] = tsv_path

    logger.info(f"QC reports written to {output_dir}")
    return files
