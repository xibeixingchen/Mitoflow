# MitoFlow

**One command, one paper.**

Plant mitochondrial genome annotation & analysis platform.

---

## Overview

MitoFlow is a modern, lightweight replacement for PMGA v1 (~15 GB Perl/Python2/MAKER container). It provides complete plant mitochondrial genome annotation and downstream analysis in a single Python 3.10+ package.
MitoFlow  provides complete plant mitochondrial genome annotation and downstream analysis in a single Python 3.10+ package.


| Feature | PMGA v1 | MitoFlow |
|---------|---------|----------|
| Language | Perl + Python 2 | Python 3.10+ |
| Gene annotation | MAKER (MAFFT + GeneMark) | pyhmmer HMM + BLAST parallel |
| Container size | ~15 GB | <100 MB (pip install) |
| tRNA annotation | tRNAscan-SE only | tRNAscan-SE 2.0 + ARAGORN dual-tool |
| Visualization | External OGDraw | Built-in pyCirclize + OGDrawR integration |
| Genetic code | NCBI Table 1 | NCBI Table 1 (standard, plant mitochondria) |
| Deployment | Singularity only | pip / conda / Docker |

## Installation

### pip (recommended)

```bash
pip install mitoflow
```

### conda

```bash
conda install -c bioconda -c conda-forge mitoflow
```

### Docker

```bash
docker pull ghcr.io/mitoflow/mitoflow:latest
docker run --rm -v $(pwd):/data mitoflow annotate -i /data/mitogenome.fasta -o /data/results/
```

### External tools (optional but recommended)

MitoFlow core annotation works out-of-the-box. For full functionality:

```bash
conda install -c bioconda trnascan-se aragorn barrnap blast mafft trimal iqtree
```

| Tool | Purpose | Required |
|------|---------|----------|
| tRNAscan-SE 2.0 | tRNA annotation (high sensitivity) | Optional (ARAGORN fallback) |
| ARAGORN | tRNA annotation (complementary) | Optional |
| Barrnap | rRNA annotation | Optional |
| BLAST+ | MTPT detection, CMS chimera detection | Optional |
| MAFFT | Phylogenetic alignment | Optional |
| trimAl | Alignment trimming | Optional |
| IQ-TREE | Phylogenetic tree building | Optional |

## Quick Start

### One-command annotation

```bash
mitoflow annotate \
  -i mitogenome.fasta \
  -o results/ \
  --name "Ranunculus japonicus" \
  --cp chloroplast.fasta
```

This runs the full pipeline:
1. Load & validate FASTA
2. Protein-coding gene annotation (pyhmmer HMM search)
3. tRNA annotation (tRNAscan-SE + ARAGORN)
4. rRNA annotation (Barrnap)
5. Gene boundary correction (start/stop codons, RNA editing)
6. CDS completeness validation
7. Output GFF3 + GenBank
8. Extract CDS/Protein/tRNA/rRNA/intron FASTA
9. Five-dimensional quality control
10. MTPT (chloroplast-derived fragment) detection

### Output structure

```
results/
├── gff/
│   └── Species.gff              # GFF3 annotation
├── genbank/
│   └── Species.gbk              # GenBank format (NCBI submission-ready)
├── fasta/
│   ├── Species.CDS.fasta        # Coding sequences
│   ├── Species.Protein.fasta    # Translated proteins
│   ├── Species.tRNA.fasta       # tRNA sequences
│   ├── Species.rRNA.fasta       # rRNA sequences
│   ├── Species.Gene.fasta       # Full gene sequences (with introns)
│   └── Species.intron.fasta     # Intron sequences
└── report/
    └── Species_mtpt.txt         # MTPT report (if --cp provided)
```

## CLI Commands

### `annotate` — Full annotation pipeline

```bash
mitoflow annotate -i mito.fasta -o results/ [options]

Options:
  -n, --name TEXT         Species/project name
  -t, --threads INT       Number of threads (default: 4)
  --db PATH               Custom database directory
  --cp PATH               Chloroplast genome FASTA (enables MTPT)
  --bam PATH              BAM file for coverage QC
  --skip-trna             Skip tRNA annotation
  --skip-rrna             Skip rRNA annotation
  --skip-qc               Skip QC checks
```

### `qc` — Five-dimensional quality control

```bash
mitoflow qc -i mito.fasta -o qc_results/ [options]
```

Evaluates assemblies across five dimensions:

| Dimension | Weight | Checks |
|-----------|--------|--------|
| Completeness | 35% | Core gene presence (41 PCGs, 3 rRNAs, tRNAs) |
| Correctness | 25% | Coverage uniformity, base accuracy |
| Contiguity | 15% | Contig count, N50, circularity, size sanity |
| Contamination | 15% | GC anomaly, chloroplast vs MTPT, nuclear contamination |
| Structure | 10% | Large repeat consistency, topology validation |

Outputs a 0-100 score with letter grade (A/B/C/D/F).

### `mtpt` — MTPT detection

```bash
mitoflow mtpt -i mito.fasta --cp chloroplast.fasta -o mtpt_results/
```

Detects mitochondrial plastid-derived DNA transfers. Generates:
- MTPT region list with identity, length, cp gene annotation
- tRNA origin classification (mt-native vs cp-derived)
- Dot-plot visualization (PNG)

### `rna-edit` — RNA editing prediction

```bash
mitoflow rna-edit -i annotation.gbk -o rna_edit_results/
```

Predicts C-to-U RNA editing sites:
- **Stop-gain**: CAA/CAG/CGA → UAA/UAG/UGA in ccmFC, rps10, atp9, atp6, rps11
- **Start-gain**: ACG → AUG in cox1, nad1, nad4L, rps10
- Site-level predictions with confidence scores

### `codon` — Codon usage analysis

```bash
mitoflow codon -i annotation.gbk -o codon_results/
```

Calculates:
- RSCU (Relative Synonymous Codon Usage)
- ENC (Effective Number of Codons)
- GC3s (GC content at third codon position)
- Amino acid frequency table

### `multiconf` — Multi-configuration structure

```bash
mitoflow multiconf -i mito.fasta -o multiconf_results/ [--gbk annotation.gbk]
```

Predicts subgenomic configurations from repeat-mediated recombination:
- Direct repeat sub-circles
- Inverted repeat isomers
- Optional long-read validation

### `kaks` — Ka/Ks selection pressure

```bash
mitoflow kaks -q query.gbk -r ref1.gbk -r ref2.gbk -o kaks_results/
```

Calculates dN/dS (Ka/Ks) ratios using the Nei-Gojobori method with Jukes-Cantor correction across species pairs.

### `synteny` — Synteny analysis

```bash
mitoflow synteny -i sp1.gbk -i sp2.gbk -i sp3.gbk -o synteny_results/
```

Detects collinear gene blocks across multiple mitochondrial genomes despite frequent rearrangements.

### `phylo` — Phylogenetic alignment preparation

```bash
mitoflow phylo -i sp1.gbk -i sp2.gbk -i sp3.gbk -o phylo_results/
```

Automates:
1. Shared gene extraction across species
2. MAFFT alignment per gene
3. trimAl trimming
4. Supermatrix concatenation

Output is ready for IQ-TREE / RAxML / FastTree.

### `cms` — CMS candidate gene prediction

```bash
mitoflow cms -i mito.fasta --gbk annotation.gbk -o cms_results/
```

Predicts Cytoplasmic Male Sterility candidate genes:
- Novel ORF scanning (configurable minimum length)
- Chimera detection (BLAST against mitochondrial gene database)
- Transmembrane domain prediction
- Homology to 23+ known CMS genes across 15+ species
- Multi-dimensional scoring (length, chimera, TM, expression context, conservation)

### `viz` — Genome visualization

```bash
mitoflow viz -i annotation.gbk -o genome_map.png
```

Generates OGDraw-quality circular genome maps:
- Gene arcs color-coded by functional category
- GC content plot
- Gene labels
- Output formats: PNG, SVG, PDF (300 DPI default)

Three visualization styles are available via `--style`:

| Style | Engine | Description |
|-------|--------|-------------|
| `v2` (default) | pycirclize | Built-in circular genome map with label spreading |
| `ogdraw` | R OGDrawR | Authentic OGDraw-style via R package (falls back to v2) |
| `gbdraw` | gbdraw | Publication-quality SVG-first diagrams with 50+ palettes |

```bash
# Default v2 style
mitoflow viz -i annotation.gbk -o genome_map.png

# gbdraw style with palette
mitoflow viz -i annotation.gbk -o genome_map.png --style gbdraw --palette orchid

# ogdraw style
mitoflow viz -i annotation.gbk -o genome_map.pdf --style ogdraw
```

#### gbdraw Integration (Optional)

Install gbdraw for publication-quality genome diagrams with built-in palettes, separate strand display, and GC/skew tracks:

```bash
pip install gbdraw cairosvg
# or with mitoflow:
pip install mitoflow[viz-gbdraw]
```

gbdraw features:
- 50+ built-in color palettes (default, orchid, sakura, forest, marine, sunset, etc.)
- Separate strand display (`--separate-strands`)
- GC content and GC skew tracks
- SVG-first output with optional PNG/PDF conversion via CairoSVG
- Falls back to v2 style if gbdraw is not installed

#### OGDrawR Integration (Optional)

For publication-quality OGDraw-style visualizations, install the OGDrawR R package:

```bash
Rscript -e "remotes::install_github('xibeixingchen/OGDrawR')"
```

MitoFlow will automatically detect and use OGDrawR if available. The integration:
- Provides authentic OGDraw-style visualization using the original R implementation
- Falls back to built-in pycirclize if OGDrawR is unavailable
- Automatically handles headless environments (servers without X11) by converting PNG output to PDF

**Python API:**
```python
from mitoflow.viz import draw_ogdraw_genome, check_ogdrawr_available
from mitoflow.viz import draw_with_gbdraw, check_gbdraw_available

# Check if OGDrawR is available
if check_ogdrawr_available():
    print("Using OGDrawR for visualization")

# Generate visualization (auto-detects OGDrawR)
draw_ogdraw_genome(
    genbank_path="annotation.gbk",
    output_path="genome_map.pdf",
    organism="Arabidopsis thaliana"
)

# Generate visualization with gbdraw
if check_gbdraw_available():
    draw_with_gbdraw(
        genbank_path="annotation.gbk",
        output_path="genome_map",
        organism="Arabidopsis thaliana",
        format="png",
        palette="orchid",
    )
```

### `report` — HTML report generation

```bash
mitoflow report -i annotation.gbk -o report.html [--qc-scores qc.json]
```

Self-contained HTML report with:
- Genome statistics
- Gene annotation table
- QC score visualization (if provided)
- File download links

## Architecture

```
src/mitoflow/
├── cli.py                    # Typer CLI (17 subcommands)
├── core/
│   ├── input.py              # FASTA loading, multi-contig merging
│   ├── output.py             # Output directory management
│   └── pipeline.py           # Pipeline orchestrator (10-step)
├── models/
│   ├── genome.py             # GenomeSequence, ContigInfo (Pydantic)
│   ├── gene.py               # GeneAnnotation, ExonRecord, Strand
│   ├── feature.py            # tRNAAnnotation, rRNAAnnotation
│   └── gff.py                # GFF3Record
├── annotate/
│   ├── pcg.py                # Protein-coding gene annotation (pyhmmer)
│   ├── trna.py               # tRNA annotation (tRNAscan-SE + ARAGORN)
│   ├── rrna.py               # rRNA annotation (Barrnap)
│   ├── boundary.py           # Gene boundary correction
│   ├── cds_check.py          # CDS completeness validation
│   └── gff_handler.py        # GFF3/GenBank writer
├── extract/
│   └── sequences.py          # Sequence extraction (CDS/Protein/tRNA/rRNA/intron/gene)
├── db/
│   ├── builder.py            # HMM database builder
│   └── manager.py            # Database manager (aliases, metadata)
├── qc/
│   ├── qc_engine.py          # QC orchestrator
│   ├── completeness.py       # Gene completeness assessment
│   ├── contiguity.py         # Assembly contiguity
│   ├── correctness.py        # Coverage & base accuracy
│   ├── contamination.py      # Contamination detection
│   ├── structure.py          # Assembly structure validation
│   └── scorer.py             # Weighted scoring (5 dimensions)
├── mtpt/
│   └── detector.py           # MTPT detection & dot-plot
├── rna_edit/
│   └── predictor.py          # RNA editing site prediction
├── codon/
│   └── analysis.py           # Codon usage (RSCU/ENC/GC3s)
├── multiconf/
│   └── repeat_mediated.py    # Multi-configuration prediction
├── kaks/
│   └── calculator.py         # Ka/Ks selection pressure
├── synteny/
│   └── collinear.py          # Synteny block detection
├── phylo/
│   ├── alignment.py          # Phylogenetic alignment pipeline
│   └── tree.py               # IQ-TREE wrapper
├── cms/
│   └── predictor.py          # CMS candidate gene prediction
├── repeat/
│   ├── ssr.py                # SSR detection
│   ├── tandem.py             # Tandem repeat detection
│   └── long_repeat.py        # Dispersed repeat detection
├── numt/
│   └── detector.py           # NUMT detection
├── viz/
│   ├── circos_plot_v2.py     # Circular genome map (pycirclize, default)
│   ├── circos_plot_ogdraw.py # OGDrawR R package integration
│   ├── gbdraw_plot.py        # gbdraw Python integration (50+ palettes)
│   ├── linear.py             # Linear genome map (pyGenomeViz)
│   ├── gc_content.py         # GC content profile plots
│   ├── config.py             # Centralized color scheme (single source of truth)
│   └── ogdrawr_wrapper.R     # R script wrapper for OGDrawR
├── report/
│   └── generator.py          # HTML report generation
└── data/
    ├── gene_info/
    │   └── gene_categories.json   # 323 products, 782 aliases, 16 categories
    ├── hmm_profiles/pcg/          # 46 HMM profiles (MAFFT-aligned)
    ├── blast_refs/
    │   ├── pcg/                   # 46 protein reference FASTA
    │   ├── rrna/                  # 3 rRNA reference FASTA (general)
    │   ├── rrna_mito/             # 3 rRNA reference FASTA (mitochondrial-specific)
    │   └── trna/                  # tRNA reference FASTA
    └── cms/
        ├── cms_reference.json     # 23 known CMS genes
        └── cms_proteins.*         # CMS BLAST database
```

## Reference Database

MitoFlow ships with a built-in reference database derived from PMGA v1:

- **46 HMM profiles** for protein-coding genes (built from multi-species MAFFT alignments)
- **46 protein reference FASTA** for BLAST fallback
- **3 rRNA reference FASTA** (5S, 18S, 26S)
- **323 gene products** with standardized naming
- **782 gene aliases** for cross-tool compatibility
- **23 known CMS genes** from 15+ plant species

Gene categories in the database:
- Core Complex I (nad1-9, 9 genes)
- Core Complex III (cob, 1 gene)
- Core Complex IV (cox1-3, 3 genes)
- Core Complex V (atp1/4/6/8/9, 5 genes)
- Ccm biogenesis (ccmB/C/FC/FN, 4 genes)
- Ribosomal proteins (rpl + rps, 15 genes)
- Rare genes (rpl6, rps8, rps15, rps16, rpl14)
- Trans-splicing genes (nad1, nad2 with 5 exons each)
- Special start/stop handling for RNA editing genes

## Biological Notes

### Genetic Code

Plant mitochondria use the **standard genetic code (NCBI Table 1)**, NOT the vertebrate mitochondrial code (Table 2). MitoFlow enforces this throughout.

### RNA Editing

Plant mitochondrial transcripts undergo C-to-U editing. MitoFlow handles two types:

- **Stop-gain**: CAA→UAA, CAG→UAG, CGA→UGA in ccmFC, rps10, atp9, atp6, rps11
- **Start-gain**: ACG→AUG in cox1, nad1, nad4L, rps10

### Trans-splicing

Genes nad1, nad2, nad5 may have exons scattered across the genome (trans-splicing). Each has up to 5 exons that are independently transcribed and spliced together.

### Special Gene Handling

| Gene | Quirk |
|------|-------|
| mttB | Accepts ATA as start codon |
| rpl16 | Accepts GTG; first 108 bp may need truncation if gene >330 bp |
| rps4 | ACG start codon is "probably correct" |
| rpl16 | Truncation: remove first 108 bp if total >330 bp |

## Dependencies

Core (installed with pip):
- biopython >= 1.79
- pyhmmer >= 0.7
- typer >= 0.7
- rich >= 12
- pandas >= 1.5
- pydantic >= 2.0
- matplotlib >= 3.5
- numpy >= 1.21
- jinja2 >= 3.0

## Development

```bash
git clone https://github.com/mitoflow/mitoflow.git
cd mitoflow
pip install -e ".[dev]"
pytest
```

## Citation

If you use MitoFlow in your research, please cite:

```
MitoFlow: A modern plant mitochondrial genome annotation and analysis platform.
```

## License

MIT
