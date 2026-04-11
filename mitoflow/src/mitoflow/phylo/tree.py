"""Phylogenetic tree building wrapper around IQ-TREE.

Wraps IQ-TREE (iqtree / iqtree2 / iqtree3) for:
1. Single-gene and concatenated alignment tree inference
2. Model selection via ModelFinder
3. Bootstrap / ultrafast bootstrap support
4. Consensus tree construction
5. Tree visualization

Usage:
    from mitoflow.phylo.tree import build_tree, PhyloTreeResult

    result = build_tree(
        "concatenated.phy",
        output_dir="trees/",
        model="auto",
        bootstrap=1000,
    )
    print(result.summary())
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PhyloTreeResult:
    """Result of IQ-TREE phylogenetic tree inference."""

    tree_newick: Path = Path()
    tree_svg: Path = Path()
    model: str = ""
    log_likelihood: float = 0.0
    bootstrap_support: dict = field(default_factory=dict)   # node_id -> support
    iqtree_version: str = ""
    warnings: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== Phylogenetic Tree ===",
            f"IQ-TREE version: {self.iqtree_version or 'unknown'}",
            f"Best model: {self.model or 'unknown'}",
            f"Log-likelihood: {self.log_likelihood:.4f}",
            f"Tree file: {self.tree_newick}",
        ]
        if self.bootstrap_support:
            values = list(self.bootstrap_support.values())
            lines.append(f"Bootstrap values: {len(values)} nodes")
            if values:
                lines.append(
                    f"  Min: {min(values)}  Median: {sorted(values)[len(values)//2]}  "
                    f"Max: {max(values)}"
                )
        if self.tree_svg.exists():
            lines.append(f"Tree image: {self.tree_svg}")
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# IQ-TREE detection
# ---------------------------------------------------------------------------

_IQTREE_VARIANTS = ["iqtree3", "iqtree2", "iqtree"]


def _detect_iqtree() -> tuple[Optional[str], Optional[str]]:
    """Detect which IQ-TREE variant is installed.

    Returns:
        (executable_path, version_string) or (None, None) if not found.
    """
    for variant in _IQTREE_VARIANTS:
        path = shutil.which(variant)
        if path:
            try:
                proc = subprocess.run(
                    [path, "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                version = (proc.stdout + proc.stderr).strip().split("\n")[0]
                return path, version
            except Exception:
                return path, variant
    return None, None


# ---------------------------------------------------------------------------
# Tree building
# ---------------------------------------------------------------------------

def build_tree(
    alignment_path: str | Path,
    output_dir: str | Path,
    seq_type: str = "protein",
    model: str = "auto",
    bootstrap: int = 1000,
    threads: int = 4,
    extra_args: Optional[list[str]] = None,
    partition_file: Optional[str | Path] = None,
) -> PhyloTreeResult:
    """Run IQ-TREE to build a phylogenetic tree.

    Detects which IQ-TREE variant is installed (iqtree3, iqtree2, iqtree)
    and runs with appropriate parameters.

    Args:
        alignment_path: Path to alignment file (FASTA/PHYLIP/NEXUS).
        output_dir: Output directory for tree files.
        seq_type: "protein" or "nucleotide" (sets -st option).
        model: Substitution model. "auto" triggers ModelFinder.
               Common values: "LG+G4", "WAG+I+G4", "GTR+G4", "MFP".
        bootstrap: Number of bootstrap replicates (0 = none, 1000 typical).
                   Uses ultrafast bootstrap (-bb) by default.
        threads: Number of threads (-T).
        extra_args: Additional arguments passed to IQ-TREE.
        partition_file: Optional partition file for concatenated alignments.

    Returns:
        PhyloTreeResult with tree paths and statistics.
    """
    alignment_path = Path(alignment_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = PhyloTreeResult()

    # Detect IQ-TREE
    iqtree_bin, version = _detect_iqtree()
    if not iqtree_bin:
        result.warnings.append(
            "IQ-TREE not found. Install iqtree3, iqtree2, or iqtree."
        )
        logger.error("IQ-TREE not found in PATH")
        return result

    result.iqtree_version = version
    logger.info("Using IQ-TREE: %s (%s)", iqtree_bin, version)

    # Validate input
    if not alignment_path.exists():
        result.warnings.append(f"Alignment file not found: {alignment_path}")
        logger.error("Alignment file not found: %s", alignment_path)
        return result

    # Build command
    prefix = output_dir / "iqtree"
    cmd = [
        iqtree_bin,
        "-s", str(alignment_path),
        "-pre", str(prefix),
        "-nt", str(threads),
    ]

    # Sequence type
    if seq_type == "protein":
        cmd.extend(["-st", "AA"])
    elif seq_type == "nucleotide":
        cmd.extend(["-st", "DNA"])

    # Model selection
    if model == "auto" or model == "MFP":
        cmd.append("-m MFP")
    else:
        cmd.extend(["-m", model])

    # Bootstrap (ultrafast)
    if bootstrap > 0:
        cmd.extend(["-bb", str(bootstrap)])
        cmd.extend(["-alrt", "1000"])

    # Partition file
    if partition_file:
        partition_path = Path(partition_file)
        if partition_path.exists():
            cmd.extend(["-p", str(partition_path)])
        else:
            result.warnings.append(
                f"Partition file not found: {partition_path}"
            )

    # Extra arguments
    if extra_args:
        cmd.extend(extra_args)

    # Always redo to avoid stale results
    cmd.append("-redo")

    logger.info("Running IQ-TREE: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            cwd=str(output_dir),
        )

        # Parse log file for results
        log_path = output_dir / "iqtree.log"
        if log_path.exists():
            _parse_iqtree_log(log_path, result)

        # Locate tree files
        treefile = output_dir / "iqtree.treefile"
        if treefile.exists():
            result.tree_newick = treefile
            logger.info("Tree file: %s", treefile)
        else:
            result.warnings.append("Tree file not found after IQ-TREE run")

        # Parse bootstrap support from tree file
        if result.tree_newick.exists():
            result.bootstrap_support = _parse_bootstrap(result.tree_newick)

    except subprocess.TimeoutExpired:
        result.warnings.append("IQ-TREE timed out after 3600 seconds")
        logger.error("IQ-TREE timed out")
    except Exception as e:
        result.warnings.append(f"IQ-TREE failed: {e}")
        logger.error("IQ-TREE failed: %s", e)

    return result


def build_gene_trees(
    alignment_dir: str | Path,
    output_dir: str | Path,
    threads: int = 4,
    model: str = "auto",
    bootstrap: int = 1000,
) -> dict[str, PhyloTreeResult]:
    """Build individual gene trees for each alignment file in a directory.

    Scans for alignment files (*.fasta, *.fa, *.phy, *.nex) and runs
    IQ-TREE on each one separately.

    Args:
        alignment_dir: Directory containing alignment files.
        output_dir: Base output directory (subdirectories per gene created).
        threads: Number of threads per IQ-TREE run.
        model: Substitution model (default: auto via ModelFinder).
        bootstrap: Number of bootstrap replicates.

    Returns:
        Dict mapping gene name -> PhyloTreeResult.
    """
    alignment_dir = Path(alignment_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Find alignment files
    patterns = ["*.fasta", "*.fa", "*.phy", "*.phylip", "*.nex", "*.nexus"]
    alignment_files = []
    for pat in patterns:
        alignment_files.extend(alignment_dir.glob(pat))

    if not alignment_files:
        logger.warning("No alignment files found in %s", alignment_dir)
        return results

    logger.info("Building trees for %d alignments", len(alignment_files))

    for aln_file in sorted(alignment_files):
        gene_name = aln_file.stem
        gene_outdir = output_dir / gene_name
        gene_outdir.mkdir(exist_ok=True)

        logger.info("Building tree for %s", gene_name)

        result = build_tree(
            alignment_path=aln_file,
            output_dir=gene_outdir,
            model=model,
            bootstrap=bootstrap,
            threads=max(1, threads),
        )
        results[gene_name] = result

    # Summary
    n_success = sum(1 for r in results.values() if r.tree_newick.exists())
    logger.info(
        "Gene trees complete: %d/%d successful",
        n_success, len(results),
    )

    return results


def draw_tree(
    tree_path: str | Path,
    output_path: str | Path,
    format: str = "png",
    dpi: int = 300,
    title: str = "",
    branch_length: bool = True,
    support_values: bool = True,
) -> Path:
    """Draw phylogenetic tree using matplotlib and BioPython Phylo.

    Args:
        tree_path: Path to Newick tree file.
        output_path: Output image path (extension sets format).
        format: Image format: "png", "pdf", "svg".
        dpi: Resolution for raster formats.
        title: Optional title for the figure.
        branch_length: Whether to draw branch lengths to scale.
        support_values: Whether to show bootstrap support values.

    Returns:
        Path to the saved figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from Bio import Phylo as BioPhylo

    tree_path = Path(tree_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Parse tree
    tree = BioPhylo.read(str(tree_path), "newick")

    # Create figure
    fig, ax = plt.subplots(figsize=(12, max(4, len(tree.get_terminals()) * 0.3)))

    BioPhylo.draw(
        tree,
        axes=ax,
        do_show=False,
        branch_labels=lambda c: (
            f"{c.confidence:.0f}" if support_values and c.confidence else ""
        ),
    )

    if title:
        ax.set_title(title, fontsize=12, fontweight="bold")

    if not branch_length:
        ax.set_xlim(auto=True)

    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    logger.info("Wrote tree image: %s", output_path)
    return output_path


def consensus_tree(
    tree_files: list[str | Path],
    output_path: str | Path,
    min_support: float = 0.5,
    threads: int = 4,
) -> PhyloTreeResult:
    """Build consensus tree from multiple gene trees using IQ-TREE.

    Concatenates the input tree files and runs IQ-TREE consensus construction.

    Args:
        tree_files: List of Newick tree file paths.
        output_path: Path for consensus tree output.
        min_support: Minimum support threshold for consensus (0-1).
        threads: Number of threads.

    Returns:
        PhyloTreeResult for the consensus tree.
    """
    output_path = Path(output_path)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    result = PhyloTreeResult()

    iqtree_bin, version = _detect_iqtree()
    if not iqtree_bin:
        result.warnings.append("IQ-TREE not found")
        return result

    result.iqtree_version = version

    # Validate tree files
    valid_trees = []
    for tf in tree_files:
        tf = Path(tf)
        if tf.exists():
            valid_trees.append(tf)
        else:
            result.warnings.append(f"Tree file not found: {tf}")

    if not valid_trees:
        result.warnings.append("No valid tree files provided")
        return result

    # Concatenate trees into a single file (one tree per line)
    trees_input = output_dir / "all_trees.tre"
    with open(trees_input, "w") as f:
        for tf in valid_trees:
            content = tf.read_text().strip()
            if content:
                f.write(content + "\n")

    # Build consensus using IQ-TREE -t CONS
    prefix = output_dir / "consensus"
    cmd = [
        iqtree_bin,
        "-t", str(trees_input),
        "-cons",
        "-minsup", str(min_support),
        "-pre", str(prefix),
        "-nt", str(threads),
        "-redo",
    ]

    logger.info("Building consensus tree: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(output_dir),
        )

        consensus_file = output_dir / "consensus.treefile"
        if consensus_file.exists():
            result.tree_newick = consensus_file
            # Copy to requested output path if different
            if consensus_file != output_path:
                shutil.copy2(str(consensus_file), str(output_path))
                result.tree_newick = output_path
            logger.info("Consensus tree: %s", result.tree_newick)
        else:
            result.warnings.append("Consensus tree file not generated")

    except subprocess.TimeoutExpired:
        result.warnings.append("IQ-TREE consensus timed out")
    except Exception as e:
        result.warnings.append(f"Consensus tree failed: {e}")

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_iqtree_log(log_path: Path, result: PhyloTreeResult) -> None:
    """Parse IQ-TREE log file for model, likelihood, and warnings."""
    try:
        content = log_path.read_text(errors="replace")
    except Exception:
        return

    # Best-fit model
    model_match = re.search(
        r"Best-fit model:\s*(\S+)", content
    )
    if model_match:
        result.model = model_match.group(1)

    # Log-likelihood
    ll_match = re.search(
        r"Log-likelihood:\s*([-\d.eE+]+)", content
    )
    if ll_match:
        try:
            result.log_likelihood = float(ll_match.group(1))
        except ValueError:
            pass

    # Warnings from IQ-TREE
    for line in content.split("\n"):
        if "WARNING" in line.upper():
            result.warnings.append(line.strip())


def _parse_bootstrap(tree_path: Path) -> dict[int, int]:
    """Parse bootstrap values from a Newick tree file.

    Returns:
        Dict mapping internal node index -> bootstrap support value.
    """
    bootstrap = {}
    try:
        content = tree_path.read_text().strip()
        # Find all confidence values (integers before colons or before closing
        # parentheses in Newick format)
        values = re.findall(r"\)(\d+):", content)
        values += re.findall(r"\)(\d+);", content)
        for i, val in enumerate(values):
            bootstrap[i] = int(val)
    except Exception:
        pass
    return bootstrap
