"""
OGDraw-style circular genome visualization for MitoFlow.

This module provides publication-quality circular genome maps using the OGDrawR R package:
- Gene arcs color-coded by functional category
- Inner/outer rings for strand orientation  
- GC content deviation plot
- Clear gene labeling
- tRNA/rRNA support

The module can use either:
1. Native Python implementation (pycirclize) - fallback mode
2. OGDrawR R package - high-quality OGDraw-style visualization

Usage:
    from mitoflow.viz.circos_plot_ogdraw import draw_genome_map
    
    draw_genome_map(
        genbank_path="annotation.gbk",
        output_path="genome_map.png",
        organism="Arabidopsis thaliana",
    )
"""

from __future__ import annotations
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Set
import numpy as np
from collections import defaultdict

from .config import ColorConfig, CATEGORY_LABELS

logger = logging.getLogger(__name__)

# Single source of truth for colors and gene classification
_color_config = ColorConfig()


def classify_gene(name: str, ftype: str = "CDS") -> str:
    """Classify gene into functional category using centralized config."""
    return _color_config.classify_gene(name, ftype)


def get_color(category: str) -> Tuple[float, float, float]:
    """Get RGB color (0-1 range) for category using centralized config."""
    return _color_config.get_rgb01(category)


@dataclass
class Gene:
    """Gene feature for visualization."""
    name: str
    start: int
    end: int
    strand: int
    ftype: str
    category: str = ""
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    
    def __post_init__(self):
        self.category = classify_gene(self.name, self.ftype or "CDS")
        self.color = get_color(self.category)
    
    @property
    def length(self) -> int:
        return self.end - self.start


def parse_features(gb_path: Path, min_len: int = 100) -> List[Gene]:
    """Parse gene features from GenBank."""
    from Bio import SeqIO
    
    record = SeqIO.read(gb_path, "genbank")
    genes = []
    seen = {}  # Track best (longest) feature per gene name
    
    for feat in record.features:
        # Only process main gene features
        if feat.type not in ("gene", "CDS", "tRNA", "rRNA"):
            continue
        
        # Get gene name
        name = (feat.qualifiers.get("gene", [""])[0] or 
                feat.qualifiers.get("locus_tag", [""])[0] or
                feat.qualifiers.get("product", [""])[0][:20])
        
        if not name:
            continue
        
        start = int(feat.location.start)
        end = int(feat.location.end)
        length = end - start
        
        # Skip very short features
        if length < min_len:
            continue
        
        strand = feat.location.strand or 1
        
        gene = Gene(name=name, start=start, end=end, 
                   strand=strand, ftype=feat.type)
        
        # Keep longest feature per gene name
        if name not in seen or length > seen[name].length:
            seen[name] = gene
    
    genes = list(seen.values())
    genes.sort(key=lambda g: g.start)
    
    logger.info(f"Parsed {len(genes)} unique genes from {gb_path}")
    return genes


def check_ogdrawr_available() -> bool:
    """Check if OGDrawR R package is available."""
    r_executable = shutil.which("Rscript")
    if not r_executable:
        logger.debug("Rscript not found in PATH")
        return False
    
    try:
        # Check if OGDrawR package is installed
        cmd = [
            r_executable,
            "-e",
            "suppressPackageStartupMessages(require(OGDrawR, quietly = TRUE)); cat(ifelse('OGDrawR' %in% loadedNamespaces(), 'TRUE', 'FALSE'))"
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        if result.returncode == 0 and "TRUE" in result.stdout:
            return True
        
        # Check R library paths for OGDrawR
        cmd = [r_executable, "-e", "cat(.libPaths()[1])"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lib_path = Path(result.stdout.strip())
            ogdrawr_path = lib_path / "OGDrawR"
            if ogdrawr_path.exists():
                return True
        
        return False
    except Exception as e:
        logger.debug(f"Error checking OGDrawR availability: {e}")
        return False


def _draw_with_ogdrawr(
    genbank_path: Path,
    output_path: Path,
    organism: str = "",
) -> bool:
    """
    Draw genome map using OGDrawR R package.
    
    Args:
        genbank_path: Input GenBank file
        output_path: Output image file
        organism: Organism name for center label
        
    Returns:
        True if successful, False otherwise
    """
    r_executable = shutil.which("Rscript")
    if not r_executable:
        logger.warning("Rscript not found, cannot use OGDrawR")
        return False
    
    # Find wrapper script
    wrapper_script = Path(__file__).parent / "ogdrawr_wrapper.R"
    if not wrapper_script.exists():
        logger.warning(f"OGDrawR wrapper script not found: {wrapper_script}")
        return False
    
    try:
        cmd = [
            r_executable,
            str(wrapper_script),
            str(genbank_path),
            str(output_path),
            organism or "Mitochondrial Genome"
        ]
        
        logger.info(f"Running OGDrawR: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"OGDrawR successfully created: {output_path}")
            if result.stdout:
                logger.debug(f"OGDrawR stdout: {result.stdout}")
            return True
        else:
            logger.warning(f"OGDrawR failed with code {result.returncode}")
            if result.stderr:
                logger.debug(f"OGDrawR stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.warning("OGDrawR execution timed out")
        return False
    except Exception as e:
        logger.warning(f"Error running OGDrawR: {e}")
        return False


def _draw_with_pycirclize(
    genbank_path: Path,
    output_path: Path,
    organism: str = "",
    figsize: Tuple[int, int] = (12, 12),
    dpi: int = 300,
    show_gc: bool = True,
    show_labels: bool = True,
) -> Path:
    """
    Draw genome map using Python pycirclize (fallback method).
    
    Args:
        genbank_path: Input GenBank file
        output_path: Output image file (.png/.pdf/.svg)
        organism: Organism name for center label
        figsize: Figure size (width, height) in inches
        dpi: Output resolution
        show_gc: Show GC content plot
        show_labels: Show gene labels
    
    Returns:
        Path to output image
    """
    from pycirclize import Circos
    from pycirclize.parser import Genbank
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    
    # Parse data
    gbk = Genbank(str(genbank_path))
    seqid2size = gbk.get_seqid2size()
    seqid2seq = gbk.get_seqid2seq()
    genes = parse_features(genbank_path)
    
    if not genes:
        raise ValueError("No genes found in GenBank file!")
    
    # Create circos
    circos = Circos(sectors=seqid2size, space=0)
    used_categories: Set[str] = set()
    
    for sector in circos.sectors:
        seq = seqid2seq.get(sector.name, "")
        size = sector.size
        
        sector_genes = [g for g in genes if g.start < size]
        fwd = [g for g in sector_genes if g.strand == 1]
        rev = [g for g in sector_genes if g.strand == -1]
        
        # Forward strand track (outer)
        fwd_track = sector.add_track((86, 94))
        fwd_track.axis(fc="#f5f5f5", ec="gray", lw=0.3)
        
        # Reverse strand track (inner)
        rev_track = sector.add_track((78, 86))
        rev_track.axis(fc="#f5f5f5", ec="gray", lw=0.3)
        
        # Draw genes
        for gene in fwd:
            used_categories.add(gene.category)
            try:
                fwd_track.arrow(
                    (gene.start, gene.end),
                    color=gene.color,
                    ec="black",
                    lw=0.4,
                    alpha=0.9,
                    head_length=min(500, gene.length * 0.3),
                )
            except Exception:
                pass
        
        for gene in rev:
            used_categories.add(gene.category)
            try:
                rev_track.arrow(
                    (gene.start, gene.end),
                    color=gene.color,
                    ec="black",
                    lw=0.4,
                    alpha=0.9,
                    head_length=min(500, gene.length * 0.3),
                )
            except Exception:
                pass
        
        # Gene labels
        if show_labels:
            for gene in sector_genes:
                if gene.length < 300:  # Only label larger genes
                    continue
                
                pos = (gene.start + gene.end) // 2
                
                try:
                    sector.text(
                        gene.name,
                        r=94 if gene.strand == 1 else 76,
                        theta=sector.pos2theta(pos),
                        size=4.5,
                        color="black",
                        ha="center",
                        va="center",
                    )
                except Exception:
                    pass
        
        # GC content
        if show_gc and seq:
            gc_track = sector.add_track((50, 76))
            gc_track.axis(fc="#fafafa", ec="gray", lw=0.3)
            
            try:
                window = 500
                positions = []
                gc_vals = []
                
                for i in range(0, len(seq) - window, window // 2):
                    chunk = str(seq[i:i+window]).upper()
                    gc = (chunk.count("G") + chunk.count("C")) / len(chunk) * 100
                    positions.append(i + window // 2)
                    gc_vals.append(gc)
                
                if positions:
                    mean_gc = np.mean(gc_vals)
                    devs = np.array(gc_vals) - mean_gc
                    max_dev = max(abs(devs.max()), abs(devs.min()), 0.1)
                    
                    # Scale to track
                    track_h = 26  # 76 - 50
                    center = 63
                    scaled = (devs / max_dev) * (track_h / 2)
                    
                    # Plot bands
                    for i in range(len(positions) - 1):
                        p0, p1 = positions[i], positions[i+1]
                        v0, v1 = scaled[i], scaled[i+1]
                        
                        if v0 > 0 or v1 > 0:
                            gc_track.fill_between(
                                [p0, p1],
                                [center + max(0,v0), center + max(0,v1)],
                                [center, center],
                                color="#444444", alpha=0.7
                            )
                        if v0 < 0 or v1 < 0:
                            gc_track.fill_between(
                                [p0, p1],
                                [center + min(0,v0), center + min(0,v1)],
                                [center, center],
                                color="#aaaaaa", alpha=0.5
                            )
                    
                    # Mean line
                    gc_track.line([0, size], [center, center], 
                                 color="red", lw=0.5, ls="--")
            except Exception as e:
                logger.debug(f"GC plot error: {e}")
        
        # Scale ticks
        fwd_track.xticks_by_interval(
            10000,
            label_formatter=lambda v: f"{v/1000:.0f}kb",
            label_size=5,
            outer=True,
        )
    
    # Center text
    lines = []
    if organism:
        lines.append(organism)
    total = sum(seqid2size.values())
    lines.append(f"{total:,} bp")
    if seq:
        gc_pct = (seq.upper().count("G") + seq.upper().count("C")) / len(seq) * 100
        lines.append(f"GC: {gc_pct:.1f}%")
    
    circos.text("\n".join(lines), size=12, ha="center", va="center", 
               weight="bold", color="#333333")
    
    # Plot
    fig = circos.plotfig(figsize=figsize)
    
    # Legend
    order = ["complex_i", "complex_ii", "complex_iii", "complex_iv", 
             "complex_v", "ccm", "rps", "rpl", "maturase", "transport",
             "trna", "rrna", "other_cds"]
    
    handles = []
    for cat in order:
        if cat in used_categories:
            handles.append(Patch(
                facecolor=get_color(cat),
                edgecolor="black",
                linewidth=0.5,
                label=CATEGORY_LABELS.get(cat, cat)
            ))
    
    if handles:
        fig.legend(
            handles=handles,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.02),
            fontsize=7,
            ncol=min(4, len(handles)),
            frameon=True,
            fancybox=True,
        )
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        dpi=dpi,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
        pad_inches=0.3,
    )
    plt.close(fig)
    
    logger.info(f"Genome map saved: {output_path}")
    return output_path


def draw_genome_map(
    genbank_path: Path | str,
    output_path: Path | str,
    organism: str = "",
    figsize: Tuple[int, int] = (12, 12),
    dpi: int = 300,
    show_gc: bool = True,
    show_labels: bool = True,
    use_ogdrawr: bool = True,
) -> Path:
    """
    Draw OGDraw-style circular genome map.
    
    By default, attempts to use the OGDrawR R package for high-quality
    visualization. Falls back to Python pycirclize implementation if
    OGDrawR is not available.
    
    Args:
        genbank_path: Input GenBank file
        output_path: Output image file (.png/.pdf/.svg)
        organism: Organism name for center label
        figsize: Figure size (width, height) in inches (Python fallback only)
        dpi: Output resolution (Python fallback only)
        show_gc: Show GC content plot (Python fallback only)
        show_labels: Show gene labels (Python fallback only)
        use_ogdrawr: Try to use OGDrawR R package (default: True)
    
    Returns:
        Path to output image
    """
    genbank_path = Path(genbank_path)
    output_path = Path(output_path)
    
    if not genbank_path.exists():
        raise FileNotFoundError(f"GenBank file not found: {genbank_path}")
    
    # Try OGDrawR first if requested
    if use_ogdrawr:
        if check_ogdrawr_available():
            logger.info("Using OGDrawR for visualization")
            if _draw_with_ogdrawr(genbank_path, output_path, organism):
                return output_path
            else:
                logger.warning("OGDrawR failed, falling back to pycirclize")
        else:
            logger.info("OGDrawR not available, using pycirclize fallback")
    
    # Fall back to Python implementation
    return _draw_with_pycirclize(
        genbank_path=genbank_path,
        output_path=output_path,
        organism=organism,
        figsize=figsize,
        dpi=dpi,
        show_gc=show_gc,
        show_labels=show_labels,
    )


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python circos_plot_ogdraw.py <input.gbk> <output.png> [organism_name]")
        sys.exit(1)
    
    # Allow command-line override of use_ogdrawr
    use_r = True
    if "--no-r" in sys.argv:
        use_r = False
        sys.argv.remove("--no-r")
    
    draw_genome_map(
        genbank_path=sys.argv[1],
        output_path=sys.argv[2],
        organism=sys.argv[3] if len(sys.argv) > 3 else "",
        use_ogdrawr=use_r,
    )
