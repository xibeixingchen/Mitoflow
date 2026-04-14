# Architecture — MitoFlow

**Mapped:** 2026-04-14

## Pattern

**CLI-driven pipeline** with modular analysis modules. Each module is independent and can be invoked separately via CLI commands.

Entry point: `mitoflow.cli:app` (Typer multi-command CLI)

## Layers

```
┌─────────────────────────────────────────────────────┐
│  CLI Layer (cli.py)                                  │
│  Typer commands → parse args, call modules           │
├─────────────────────────────────────────────────────┤
│  Core Pipeline (core/)                               │
│  pipeline.py → orchestrate annotation steps          │
│  input.py → FASTA loading/validation                 │
│  output.py → OutputManager (directory layout)        │
├─────────────────────────────────────────────────────┤
│  Analysis Modules (each is independent)              │
│  annotate/  qc/  mtpt/  rna_edit/  codon/           │
│  kaks/  phylo/  synteny/  pi/  cms/  repeat/        │
│  numt/  multiconf/                                   │
├─────────────────────────────────────────────────────┤
│  Data Models (models/)                               │
│  genome.py → GenomeSequence, ContigInfo              │
│  gene.py → GeneAnnotation, ExonRecord, Strand        │
│  feature.py → tRNAAnnotation, rRNAAnnotation         │
│  gff.py → GFF3/GenBank parsing/writing               │
├─────────────────────────────────────────────────────┤
│  Database (db/)                                      │
│  manager.py → DBManager (reference data access)      │
│  builder.py → Database building                      │
├─────────────────────────────────────────────────────┤
│  Visualization (viz/ + per-module visualize.py)      │
│  viz/ → circos_plot_v2, gbdraw_plot, linear, etc.    │
│  Each module has own visualize.py + visualize_r.py   │
├─────────────────────────────────────────────────────┤
│  Data Layer (data/)                                  │
│  hmm_profiles/ blast_refs/ gene_info/ cms/           │
└─────────────────────────────────────────────────────┘
```

## Data Flow (Annotation Pipeline)

```
FASTA input
    │
    ▼
load_fasta() ──► GenomeSequence (pydantic model)
    │
    ├──► annotate_pcg() ──► pyhmmer HMM search + tblastn refinement
    │         │               ──► GeneAnnotation list
    │         └──► validate_trans_spliced_genes()
    │
    ├──► annotate_trna() ──► tRNAscan-SE + ARAGORN
    │         └──► tRNAAnnotation list
    │
    ├──► annotate_rrna() ──► Barrnap
    │         └──► rRNAAnnotation list
    │
    ├──► correct_boundaries() ──► Gene boundary refinement
    │
    ├──► validate_cds() ──► CDS completeness check
    │
    ├──► write_gff3() + write_genbank() ──► Output files
    │
    ├──► extract_all() ──► Extract CDS/Protein/tRNA/rRNA/intron FASTA
    │
    ├──► QCEngine.run() ──► Five-dimensional QC assessment
    │
    └──► detect_mtpt() ──► MTPT region detection (optional)
```

## Module Independence

Each analysis module (qc, mtpt, rna_edit, codon, kaks, phylo, synteny, pi, cms, repeat, numt, multiconf) follows the same pattern:

1. **`detector.py` / `predictor.py` / `analysis.py`** — Core computation
2. **`visualize.py`** — Python-based visualization (matplotlib)
3. **`visualize_r.py`** — R-based visualization (via Rscript subprocess)
4. **`__init__.py`** — Public API exports

Most modules can operate standalone given a FASTA or GenBank file.

## Key Abstractions

- **`GenomeSequence`** (`models/genome.py`) — Pydantic model with computed fields for length, GC%, reverse complement
- **`GeneAnnotation`** (`models/gene.py`) — Pydantic model with exon list, strand, confidence scores
- **`DBManager`** (`db/manager.py`) — Centralized reference data access with caching (`@lru_cache`)
- **`OutputManager`** (`core/output.py`) — Lazy directory creation for output files
- **`PipelineConfig`** / **`PipelineResult`** (`core/pipeline.py`) — Dataclass configuration and results

## Entry Points

1. **CLI** (`src/mitoflow/cli.py`) — 17 commands: annotate, extract, qc, mtpt, viz, rna_edit, codon, multiconf, db, kaks, synteny, pi, phylo, cms, report, repeat, numt, gc, phylo-tree
2. **Python API** — Each module can be imported and used programmatically
3. **Batch scripts** (`scripts/run_gold_standard_batch.sh`) — Batch validation against gold standard genomes

## Visualization Architecture

Dual visualization system:
- **Python plots** (`visualize.py`) — matplotlib-based, cross-platform
- **R plots** (`visualize_r.py`) — R/ggplot2-based, higher quality but requires R
- **viz/** module — Specialized genome visualization (circular maps via pycirclize/gbdraw/pygenomeviz)
