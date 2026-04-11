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

## Architecture

### Package Structure

Source lives in `src/mitoflow/` with 20 submodules. The CLI entry point is `mitoflow.cli:app` (Typer).

```
cli.py              -> 17 Typer subcommands (annotate, qc, mtpt, viz, rna-edit, codon, etc.)
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

## Visualization Backends

Two visualization backends:

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
