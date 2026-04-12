# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## Project Overview

MitoFlow is a Python 3.10+ package for plant mitochondrial genome annotation and downstream analysis. It replaces PMGA v1 (a ~15 GB Perl/Python2/MAKER container) with a pip-installable package. Version 0.1.0, actively in development.

**Important**: Plant mitochondria use the **standard genetic code (NCBI Table 1)**, NOT the vertebrate mitochondrial code.

## Build & Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install with gbdraw (Python 3.10+ required)
conda create -n mitoflow310 python=3.10 -y
conda run -n mitoflow310 pip install -e . -e "/path/to/gbdraw"

# Run all tests
pytest

# Run the CLI
mitoflow --help
mitoflow annotate -i mitogenome.fasta -o results/ --name "Species name"
```

No linter or type-checker is configured (no ruff, mypy, or black config).

### R Environment Setup

The R visualization layer requires R 4.x with the following packages:

```bash
# Core R packages for all module visualization
Rscript -e "install.packages(c('ggplot2', 'dplyr', 'tidyr', 'eoffice'))"

# NUMT ideogram (optional)
Rscript -e "install.packages('RIdeogram')"

# RIdeogram also needs rsvg for SVG→PNG conversion
Rscript -e "install.packages('rsvg')"
```

The system R is at `/home/jiazc/software/R-4.4.2/`. The Makeconf was reconstructed from scratch — do NOT overwrite it. See `Makeconf.bak_codex_empty` for the broken backup.

**Known conda/system library conflicts**: The conda `mitoflow310` environment's shared libraries (libxml2, libgobject, libicuuc) conflict with system R. If R packages fail to load with segfaults, the fix is to rebuild the conflicting R package from CRAN source so it links to system libraries instead of conda libraries. Example: `remove.packages("XML"); install.packages("XML")`.

## Architecture

### Package Structure

Source lives in `src/mitoflow/` with 20+ submodules. The CLI entry point is `mitoflow.cli:app` (Typer).

```
cli.py              -> 18 Typer subcommands (annotate, qc, mtpt, viz, rna-edit, codon, etc.)
core/               -> I/O (input.py), output management (output.py), pipeline orchestrator (pipeline.py)
models/             -> Pydantic data models (genome.py, gene.py, feature.py, gff.py)
annotate/           -> Gene annotation: PCG (pyhmmer HMM), tRNA (dual-tool), rRNA, boundary correction, CDS validation, GFF/GenBank writer
extract/            -> Sequence extraction (CDS/Protein/tRNA/rRNA/intron/gene FASTA)
db/                 -> Reference database management (manager.py) and builder (builder.py)
qc/                 -> Five-dimensional quality control (completeness 35%, correctness 25%, contiguity 15%, contamination 15%, structure 10%)
mtpt/               -> Mitochondrial plastid-derived DNA detection
rna_edit/           -> RNA editing site prediction (C-to-U: stop-gain & start-gain)
codon/              -> Codon usage analysis (RSCU/ENC/GC3s)
multiconf/          -> Multi-configuration structure prediction from repeat-mediated recombination
kaks/               -> Ka/Ks selection pressure (Nei-Gojobori)
synteny/            -> Synteny block detection across genomes + visualization (gbdraw + pyGenomeViz)
phylo/              -> Phylogenetic alignment pipeline (MAFFT + trimAl + supermatrix)
cms/                -> CMS candidate gene prediction (novel ORF + chimera + transmembrane)
repeat/             -> SSR, tandem, and long repeat detection
numt/               -> NUMT detection
viz/                -> Genome visualization: gbdraw (Python, default) + OGDrawR (R, for reports)
report/             -> HTML report generation
data/               -> Bundled reference data (HMM profiles, BLAST refs, gene metadata JSON)
```

### Data Flow (Annotation Pipeline)

```
FASTA -> load_fasta() -> GenomeSequence (Pydantic)
  -> annotate PCG (pyhmmer HMM search + BLAST fallback for divergent genes)
  -> annotate tRNA (tRNAscan-SE + ARAGORN dual-tool with merge logic)
  -> annotate rRNA (Barrnap + BLAST fallback)
  -> correct_boundaries() (start/stop codons, RNA editing)
  -> validate_cds()
  -> write GFF3 + GenBank
  -> extract sequences (CDS/Protein/tRNA/rRNA/intron/gene)
  -> optional: QC (5-dim scoring), MTPT detection, report generation
```

### Key Design Patterns

- **Pydantic models** for all core data structures (`GenomeSequence`, `GeneAnnotation`, `ExonRecord`, `tRNAAnnotation`, `rRNAAnnotation`, `GFF3Record`). `Strand` is an IntEnum (PLUS=1, MINUS=-1).
- **Pipeline orchestrator** (`core/pipeline.py`): `AnnotationPipeline` wires modules sequentially, configured via `PipelineConfig`/`PipelineResult` dataclasses.
- **Database manager** (`db/manager.py`): `DBManager` provides centralized access to reference data with `@lru_cache` for metadata. Supports custom database paths via `--db`.
- **Output manager** (`core/output.py`): `OutputManager` manages output directory layout with computed properties for all standard paths.
- **Multi-tool annotation**: each gene type uses dual tools with merge/fallback logic (e.g., tRNAscan-SE + ARAGORN, Barrnap + BLAST).

### Special Gene Handling (Hard-Coded Biological Knowledge)

- **RNA editing stop-gain**: CAA/CAG/CGA -> stop in ccmFC, rps10, atp9, atp6, rps11
- **RNA editing start-gain**: ACG -> AUG in cox1, nad1, nad4L, rps10
- **mttB**: accepts ATA as start codon
- **rpl16**: accepts GTG; first 108 bp truncated if gene >330 bp
- **Trans-splicing**: nad1, nad2, nad5 may have up to 5 scattered exons

### Bundled Reference Data (`data/`)

- 46 HMM profiles + combined database (`mitoflow_pcg.hmm`)
- 46 protein reference FASTA for BLAST fallback
- 3 rRNA reference FASTA (5S, 18S, 26S)
- 1 tRNA reference FASTA (~3086 sequences)
- 23 known CMS genes + BLAST database
- `gene_categories.json`: 323 products, 782 aliases, 16 categories with special handling rules

## Python Version

Requires Python >= 3.10 (set in `pyproject.toml`). The code uses `X | Y` union types and `list[...]` generics that require 3.10+. All modules use `from __future__ import annotations` for forward compatibility.

## R Visualization Architecture

All analysis modules (10 total) follow a consistent **R-first, matplotlib fallback** pattern:

### Module Visualization Files

Each module with R visualization has three files:

| File | Purpose |
|------|---------|
| `*_plots.R` | R script using ggplot2 + eoffice, reads TSV, outputs PNG/PDF/PPTX |
| `visualize_r.py` | Python→R bridge: writes temp TSV, calls Rscript, collects outputs |
| `visualize.py` | R-first entry point with matplotlib fallback |

### R Script Pattern

```r
# Standard header
suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(eoffice)
})

# Parse args: <input.tsv> <output_prefix> [extra_args...] [width] [height] [dpi]
# save_plot helper: ggsave PNG + PDF + eoffice::topptx() PPTX
# Each plot function: build ggplot2 object -> save_plot(p, "plot_name")
```

### Python Bridge Pattern

```python
# visualize_r.py
def check_r_<module>_available() -> bool:
    """Check R + ggplot2 + eoffice."""
    # subprocess.run([rscript, "-e", "require(ggplot2) && require(eoffice)"])

def plot_<module>_with_r(result, output_dir, prefix, dpi, ...) -> dict[str, Path]:
    """Write temp TSV -> call Rscript -> collect PNG/PDF/PPTX outputs."""
    # tempfile.NamedTemporaryFile for TSV
    # subprocess.run([rscript, r_script, tsv_path, out_prefix, ...])
    # Return {plot_name: png_path}
```

### visualize.py Pattern

```python
# visualize.py
def plot_all_<module>(result, output_dir, prefix, dpi, ...) -> dict[str, Path]:
    # Try R first
    try:
        from .visualize_r import check_r_<module>_available, plot_<module>_with_r
        if check_r_<module>_available():
            return plot_<module>_with_r(...)
    except Exception:
        logger.warning("R unavailable, falling back to matplotlib")

    # Fallback: matplotlib implementations
    ...
```

### CLI Integration

All analysis commands use standardized flags:

```python
plot: bool = typer.Option(True, "--plot/--no-plot", help="Generate visualization plots")
dpi: int = typer.Option(300, "--dpi", help="Plot resolution (DPI)")
```

After analysis completes:

```python
if plot:
    from .<module>.visualize import plot_all_<module>
    plot_dir = out.report_dir / "plots"
    plot_files = plot_all_<module>(result, output_dir=plot_dir, prefix=name, dpi=dpi, ...)
```

### Module Visualization Summary

| Module | R Script | Plots | Special R Packages |
|--------|----------|-------|--------------------|
| numt | numt_plots.R | 5 | RIdeogram (ideogram), rsvg |
| kaks | kaks_plots.R | 5 | — |
| codon | codon_plots.R | 7 | — |
| pi | pi_plots.R | 3 | — |
| rna_edit | rnaedit_plots.R | 3 | — |
| mtpt | mtpt_plots.R | 4 | — |
| qc | qc_plots.R | 3 | — |
| cms | cms_plots.R | 4 | — |
| multiconf | multiconf_plots.R | 4 | — |
| repeat | repeat_plots.R | 5 | — |

All modules use `ggplot2 + eoffice` as baseline. Only NUMT additionally requires `RIdeogram` for chromosome ideogram and `rsvg` for SVG conversion.

## Visualization Backends (Genome Maps)

Two visualization backends for circular genome maps:

| Style | Engine | Dependency | Install |
|-------|--------|-----------|---------|
| `gbdraw` (default) | gbdraw Python package | Required for Python viz | `pip install gbdraw` |
| `ogdraw` | R OGDrawR package | Required for R viz | `R -e "remotes::install_github('xibeichens/OGDrawR')"` |

- **Report generation** uses OGDrawR (R) first, falls back to gbdraw (Python)
- **Synteny visualization** uses gbdraw's linear diagram with BLAST-based comparison links (`draw_synteny_gbdraw`)
- The gbdraw wrapper is in `viz/gbdraw_plot.py` using the `gbdraw.api` Python API (`build_circular_diagram` + `save_figure_to`)
- The OGDrawR wrapper is `viz/ogdrawr_wrapper.R`, handles headless PNG via `type="cairo"`

## Color System

All visualization backends use a single color palette defined in `viz/config.py` (`ColorConfig` class). The `DEFAULT_COLORS` dict and `GENE_PREFIX_MAP` provide the canonical gene-to-category-to-color mapping. **Do not** add color definitions or `classify_gene()` functions to individual plot modules -- import from `config.py` instead.

## Conda Environment

For gbdraw (requires Python 3.10+), use the `mitoflow310` conda environment:
```bash
conda activate mitoflow310
```

## Git Subtree Push

The `mitoflow/` subdirectory is pushed to GitHub repo `xibeixingchen/Mitoflow` via git subtree:

```bash
# From the PMGA root directory
cd /home/jiazc/data16t/mito_genome/PMGA
git subtree push --prefix=mitoflow mitoflow main
```

This frequently gets SIGTERM but usually succeeds. If it fails, retry.
