# Structure — MitoFlow

**Mapped:** 2026-04-14

## Directory Layout

```
mitoflow/
├── pyproject.toml              # Build config, dependencies
├── README.md                   # English documentation
├── README_CN.md                # Chinese documentation
├── LICENSE                     # MIT
├── CODEBUDDY.md                # Code buddy instructions
├── src/
│   └── mitoflow/
│       ├── __init__.py
│       ├── cli.py              # Typer CLI (17 commands)
│       ├── core/               # Core pipeline infrastructure
│       │   ├── input.py        # FASTA loading & validation
│       │   ├── output.py       # OutputManager (directory layout)
│       │   └── pipeline.py     # AnnotationPipeline orchestrator
│       ├── models/             # Pydantic data models
│       │   ├── genome.py       # GenomeSequence, ContigInfo
│       │   ├── gene.py         # GeneAnnotation, ExonRecord, Strand
│       │   ├── feature.py      # tRNAAnnotation, rRNAAnnotation
│       │   └── gff.py          # GFF3/GenBank parsing/writing
│       ├── db/                 # Reference database management
│       │   ├── manager.py      # DBManager (data access)
│       │   └── builder.py      # Database building
│       ├── annotate/           # Gene annotation modules
│       │   ├── pcg.py          # Protein-coding gene (pyhmmer + BLAST)
│       │   ├── trna.py         # tRNA (tRNAscan-SE + ARAGORN)
│       │   ├── rrna.py         # rRNA (Barrnap)
│       │   ├── boundary.py     # Gene boundary correction
│       │   ├── cds_check.py    # CDS validation
│       │   ├── trans_splicing.py # Trans-spliced gene handling
│       │   └── gff_handler.py  # GFF3/GenBank I/O
│       ├── extract/            # Sequence extraction
│       │   └── sequences.py    # Extract CDS/Protein/tRNA/rRNA/intron
│       ├── qc/                 # Quality control (5 dimensions)
│       │   ├── qc_engine.py    # QCEngine orchestrator
│       │   ├── completeness.py # Gene completeness assessment
│       │   ├── contiguity.py   # Assembly continuity
│       │   ├── correctness.py  # Base/structural accuracy
│       │   ├── contamination.py # cp/nuclear contamination
│       │   ├── structure.py    # Repeat/topology consistency
│       │   ├── scorer.py       # Scoring & grading
│       │   ├── visualize.py    # Python QC plots
│       │   └── visualize_r.py  # R QC plots
│       ├── mtpt/               # MTPT detection
│       │   ├── detector.py     # MTPT region finder
│       │   ├── visualize.py    # Python plots
│       │   └── visualize_r.py  # R plots
│       ├── rna_edit/           # RNA editing prediction
│       │   ├── predictor.py    # C-to-U site prediction
│       │   ├── corrector.py    # Protein correction
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── codon/              # Codon usage analysis
│       │   ├── analysis.py     # RSCU, ENC, GC3s, PR2
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── kaks/               # Ka/Ks selection pressure
│       │   ├── calculator.py   # KaKs_Calculator wrapper
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── phylo/              # Phylogenetic analysis
│       │   ├── alignment.py    # Extract, align, concatenate
│       │   └── tree.py         # IQ-TREE wrapper
│       ├── synteny/            # Synteny analysis
│       │   ├── collinear.py    # Gene order collinearity
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── pi/                 # Nucleotide diversity
│       │   ├── diversity.py    # Pi calculation
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── cms/                # CMS prediction
│       │   ├── predictor.py    # CMS candidate finder
│       │   ├── report.py       # Report generation
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── repeat/             # Repeat detection
│       │   ├── ssr.py          # Simple sequence repeats
│       │   ├── tandem.py       # Tandem repeats
│       │   ├── long_repeat.py  # Dispersed/long repeats
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── numt/               # NUMT detection
│       │   ├── detector.py     # Nuclear-mito DNA segments
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── multiconf/          # Multi-configuration
│       │   ├── repeat_mediated.py # Subgenome prediction
│       │   ├── visualize.py
│       │   └── visualize_r.py
│       ├── viz/                # Genome visualization
│       │   ├── gbdraw_plot.py  # gbdraw circular maps
│       │   ├── circos_plot_v2.py # pycirclize maps
│       │   ├── circos_plot_ogdraw.py # OGDrawR maps
│       │   ├── linear.py       # Linear genome maps
│       │   ├── gc_content.py   # GC content plotting
│       │   └── config.py       # Visualization config
│       ├── report/             # HTML report generation
│       │   └── generator.py    # Jinja2-based HTML reports
│       └── data/               # Bundled reference data
│           ├── hmm_profiles/pcg/  # HMM profiles
│           ├── blast_refs/     # BLAST references
│           │   ├── pcg/       # Protein-coding gene refs
│           │   ├── pcg_new/   # Updated PCG refs
│           │   ├── pcg_v2/    # V2 PCG refs
│           │   ├── rrna/      # rRNA refs
│           │   ├── rrna_mito/ # Mitochondrial rRNA refs
│           │   ├── trna/      # tRNA refs
│           │   └── exons/     # Exon refs
│           ├── gene_info/     # Gene metadata JSON
│           └── cms/           # CMS gene database
├── tests/
│   ├── conftest.py            # Test fixtures
│   ├── test_input.py          # Input validation tests
│   ├── test_boundary_refinement.py
│   ├── test_trans_splicing.py
│   ├── test_trans_splicing_merge.py
│   ├── test_trna_naming.py
│   ├── test_gene_length_validation.py
│   └── test_data/             # Test data files
├── scripts/
│   ├── run_gold_standard_batch.sh
│   └── update_protein_database.py
├── examples/
│   └── ogdrawr_usage.py
├── deploy/
│   └── web/
│       ├── backend/main.py
│       └── frontend/app.py
├── docs/                      # Documentation
├── data/
│   └── gold_standard/         # Gold standard test genomes
│       ├── genbank/           # Reference GenBank files (~30+)
│       └── fasta/             # Reference FASTA files
├── logs/                      # Runtime logs
└── results/                   # Pipeline output
```

## Key File Locations

| Purpose | Path |
|---------|------|
| CLI entry point | `src/mitoflow/cli.py` |
| Main pipeline | `src/mitoflow/core/pipeline.py` |
| Data models | `src/mitoflow/models/` |
| Reference data | `src/mitoflow/data/` |
| Gene metadata | `src/mitoflow/data/gene_info/gene_categories.json` |
| HMM profiles | `src/mitoflow/data/hmm_profiles/pcg/` |
| Tests | `tests/` |
| Gold standard data | `data/gold_standard/` |
| Batch scripts | `scripts/` |
