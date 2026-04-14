# Stack — MitoFlow

**Mapped:** 2026-04-14

## Language & Runtime

- **Python 3.10+** (required: `>=3.10`)
- Type hints: `from __future__ import annotations` used throughout
- No async code — entirely synchronous pipeline

## Build System

- **Hatchling** (`pyproject.toml`, `[build-system]`)
- Package layout: `src/mitoflow/` (src layout)
- Entry point: `mitoflow = "mitoflow.cli:app"` (Typer CLI)

## Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `biopython` | >=1.79 | Sequence I/O, GenBank/FASTA parsing |
| `pyhmmer` | >=0.7 | HMM-based protein gene annotation |
| `typer` | >=0.7 | CLI framework |
| `rich` | >=12 | Terminal output formatting |
| `pandas` | >=1.5 | Data tables (codon usage, Ka/Ks) |
| `pydantic` | >=2.0 | Data models (GenomeSequence, GeneAnnotation) |
| `matplotlib` | >=3.5 | Visualization (GC, QC plots) |
| `numpy` | >=1.21 | Numerical computation |
| `jinja2` | >=3.0 | HTML report generation |
| `pycirclize` | >=0.3 | Circular genome visualization |
| `pygenomeviz` | >=0.5 | Linear/synteny genome visualization |

## Optional Dependencies

| Package | Purpose |
|---------|---------|
| `gbdraw` >=0.9.0 | OGDraw-quality circular genome maps (Python) |
| `cairosvg` | SVG rendering for gbdraw |
| `pyyaml` | Custom color scheme persistence |
| OGDrawR (R) | Alternative OGDraw visualization via R package |

## External Tools (CLI dependencies)

| Tool | Purpose | Detection |
|------|---------|-----------|
| `tRNAscan-SE` | tRNA gene prediction | Called via subprocess |
| `ARAGORN` | tRNA gene prediction (backup) | Called via subprocess |
| `Barrnap` | rRNA gene prediction | Called via subprocess |
| `BLAST+` (tblastn, makeblastdb) | Protein-to-genome alignment | Called via subprocess |
| `minimap2` | Read mapping for coverage | Called via subprocess |
| `samtools` | BAM processing | Called via subprocess |
| `KaKs_Calculator-3.0` | Ka/Ks selection pressure | Called via subprocess |
| `MAFFT` | Multiple sequence alignment | Called via subprocess |
| `trimAl` | Alignment trimming | Called via subprocess |
| `iqtree2`/`iqtree` | Phylogenetic tree building | Called via subprocess |
| `blastn` | Repeat detection, NUMT detection | Called via subprocess |
| `Rscript` | OGDrawR visualization, various R plots | Called via subprocess |

## Dev Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Testing framework |
| `pytest-cov` | Coverage reporting |

## Configuration

- `pyproject.toml` — build config, dependencies, pytest settings
- Test paths: `tests/`
- Python path for tests: `src/`
- No linter/formatter config (no ruff, black, mypy configs)

## Data Files (Bundled)

Located in `src/mitoflow/data/`:
- `hmm_profiles/pcg/` — HMM profiles for protein-coding genes
- `blast_refs/pcg/` — BLAST reference proteins
- `blast_refs/pcg_new/`, `blast_refs/pcg_v2/` — Updated reference versions
- `blast_refs/rrna/`, `blast_refs/rrna_mito/` — rRNA references
- `blast_refs/trna/` — tRNA references
- `blast_refs/exons/` — Exon reference sequences
- `gene_info/` — Gene metadata JSON (categories, aliases, products)
- `cms/` — CMS gene database
