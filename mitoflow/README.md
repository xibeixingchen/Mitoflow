<p align="center">
  <img src="docs/mitoflow_logo.png" alt="MitoFlow Logo" width="400"/>
</p>

<p align="center">
  <a href="README_CN.md">中文文档</a> | English
</p>

<p align="center">
  <em>One command, one paper.</em>
</p>

---

**MitoFlow** is a Python 3.10+ platform for plant mitochondrial genome annotation and comparative analysis. It automates the full workflow from raw FASTA to publication-ready outputs — annotation, codon usage, selection pressure, nucleotide diversity, synteny, and phylogenetics — all through a unified CLI.

## Features

- **Automated Annotation** — Protein-coding genes (pyhmmer HMM + BLAST), tRNAs (tRNAscan-SE + ARAGORN), rRNAs (Barrnap), with boundary correction and RNA editing support
- **Codon Usage Analysis** — RSCU, ENC, GC3s, GC12, PR2 bias plot, neutrality plot, ENC-GC3s selection plot (7 figures)
- **Ka/Ks Selection Pressure** — KaKs_Calculator-3.0 (7 methods); 5 plot types
- **Nucleotide Diversity (Pi)** — CDS & IGS Pi calculation, evolutionary hotspot detection
- **Synteny Visualization** — gbdraw linear diagram with pairwise tblastx comparison links
- **Genome Mapping** — Circular genome maps via R (OGDrawR) or Python (gbdraw); 50+ color palettes
- **Multi-configuration Structure** — Repeat-mediated recombination prediction
- **CMS Candidate Genes** — Novel ORF scanning, chimera detection, transmembrane domain prediction
- **MTPT Detection** — Chloroplast-derived fragment identification
- **NUMT Detection** — Nuclear mitochondrial DNA segment identification with RIdeogram ideogram
- **Repeat Detection** — SSR, tandem, and long/dispersed repeats
- **RNA Editing** — C-to-U site prediction (stop-gain, start-gain)
- **Quality Control** — Five-dimensional scoring (0–100)
- **Phylogenetic Pipeline** — Shared gene extraction, MAFFT alignment, supermatrix concatenation

## Quick Start

### Installation

```bash
# Core
pip install mitoflow

# With gbdraw visualization support
pip install "mitoflow[viz-gbdraw]"

# External tools (optional but recommended)
conda install -c bioconda trnascan-se aragorn barrnap blast mafft trimal iqtree

# R visualization support (optional, for publication-quality PNG/PDF/PPTX)
Rscript -e "install.packages(c('ggplot2', 'eoffice'))"
# For NUMT ideogram:
Rscript -e "install.packages('RIdeogram')"
```

### Annotate a mitochondrial genome

```bash
mitoflow annotate \
  -i mitogenome.fasta \
  -o results/ \
  --name "Arabidopsis thaliana" \
  --cp chloroplast.fasta
```

This runs the full 10-step pipeline: loading, PCG annotation, tRNA/rRNA annotation, boundary correction, CDS validation, GFF3 + GenBank output, sequence extraction, QC, and MTPT detection.

## Downstream Analyses

All analysis commands support `--plot/--no-plot` (default: plot) and `--dpi` (default: 300) options. When R with ggplot2 + eoffice is available, plots are generated in **PNG + PDF + PPTX** formats; otherwise, matplotlib fallback produces PNG only.

### Codon Usage

```bash
mitoflow codon -i annotation.gbk -o codon_results/
```

Generates 7 figures: RSCU heatmap, ENC-GC3s plot (basic + enhanced), codon usage bar, amino acid frequency, PR2 bias, neutrality plot.

### Ka/Ks Selection Pressure

```bash
mitoflow kaks -q query.gbk -r ref1.gbk -r ref2.gbk -o kaks_results/ --method MA
```

Generates 5 figures: omega barplot, omega distribution, gene heatmap, ML scatter, selection type pie. Supports 7 methods: MA, NG, LWL, LPB, GY, YN, ALL.

### Nucleotide Diversity

```bash
mitoflow pi -i sp1.gbk -i sp2.gbk -o pi_results/
```

Generates 3 figures: Pi bar chart, Pi distribution, species comparison.

### MTPT Detection

```bash
mitoflow mtpt -i mito.fasta -c chloroplast.fasta -o mtpt_results/
```

Generates 4 figures: category barplot, identity distribution, mitochondrial coverage map, gene coverage.

### NUMT Detection

```bash
mitoflow numt -i mito.fasta -n nuclear.fasta -o numt_results/
```

Generates 5 figures: RIdeogram nuclear chromosome ideogram with NUMT markers, category barplot, identity histogram, mitochondrial coverage dot plot, per-chromosome distribution.

### Repeat Detection

```bash
mitoflow repeat -i mitogenome.fasta -o repeat_results/
```

Detects SSR (microsatellite), tandem, and long/dispersed repeats. Generates 5 figures: SSR category distribution, top SSR motifs, tandem repeat period distribution, long repeat genome map with arcs, long repeat type pie chart.

### Multi-configuration Structure

```bash
mitoflow multiconf -i mitogenome.fasta -o multiconf_results/ --gbk annotation.gbk
```

Predicts subgenomic configurations from repeat-mediated recombination. Generates 4 figures: repeat map with connecting arcs, configuration diagram (master + subcircles), recombination summary, repeat type distribution.

### CMS Candidate Genes

```bash
mitoflow cms -i mitogenome.fasta --gbk annotation.gbk -o cms_results/
```

Predicts cytoplasmic male sterility candidate genes. Generates 4 figures: score breakdown (stacked bar), candidate heatmap, genome context map, confidence distribution.

### RNA Editing

```bash
mitoflow rna-edit -i annotation.gbk -o rna_edit_results/
```

Predicts C-to-U RNA editing sites. Generates 3 figures: editing sites per gene, editing type pie, codon position distribution.

### Quality Control

```bash
mitoflow qc -i mitogenome.fasta --gbk annotation.gbk -o qc_results/
```

Five-dimensional scoring (completeness, contiguity, correctness, contamination, structure). Generates 3 figures: radar chart, gauge, dimension summary.

### Synteny

```bash
mitoflow synteny -i sp1.gbk -i sp2.gbk -o synteny_results/ --viz gbdraw
```

### Genome Map

```bash
mitoflow viz -i annotation.gbk -o genome_map.png --style gbdraw --palette orchid
```

## Visualization

### R Visualization (Recommended)

When R with `ggplot2` + `eoffice` is installed, all analysis modules automatically generate publication-quality plots in three formats:

| Format | Backend | Description |
|--------|---------|-------------|
| PNG | ggplot2 + ggsave | High-resolution raster (default 300 DPI, configurable via `--dpi`) |
| PDF | ggplot2 + ggsave | Vector graphics for publication |
| PPTX | eoffice::topptx | Editable in PowerPoint/LibreOffice |

Install R visualization support:

```bash
Rscript -e "install.packages(c('ggplot2', 'eoffice'))"
# Optional: for NUMT chromosome ideogram
Rscript -e "install.packages('RIdeogram')"
```

### Matplotlib Fallback

If R is unavailable, all modules fall back to matplotlib (PNG only). No additional installation required.

### Genome Map Backends

| Backend | Language | Style | Installation |
|---------|----------|-------|--------------|
| **OGDrawR** | R | OGDraw-style circular map | `Rscript -e "remotes::install_github('xibeixingchen/OGDrawR')"` |
| **gbdraw** | Python | Publication-quality SVG/PNG, 50+ palettes | `pip install gbdraw cairosvg` |

## Output Structure

```
results/
├── gff/                       # GFF3 annotation
├── genbank/                   # GenBank format (NCBI submission-ready)
├── fasta/                     # CDS, Protein, tRNA, rRNA, Gene, Intron
└── report/                    # QC scores, MTPT report, genome map
    └── plots/                 # Visualization outputs (PNG/PDF/PPTX)
```

## CLI Commands

| Command | Description | Plots |
|---------|-------------|-------|
| `annotate` | Full annotation pipeline | — |
| `qc` | Five-dimensional quality control | 3 |
| `mtpt` | MTPT detection | 4 |
| `codon` | Codon usage analysis | 7 |
| `kaks` | Ka/Ks selection pressure | 5 |
| `pi` | Nucleotide diversity & hotspots | 3 |
| `rna-edit` | RNA editing site prediction | 3 |
| `numt` | NUMT detection | 5 |
| `repeat` | SSR + tandem + long repeats | 5 |
| `multiconf` | Multi-configuration prediction | 4 |
| `cms` | CMS candidate gene prediction | 4 |
| `synteny` | Synteny analysis & visualization | — |
| `phylo` | Phylogenetic alignment preparation | — |
| `viz` | Genome map generation | — |
| `report` | HTML report generation | — |
| `gc` | GC content analysis | — |
| `phylo-tree` | Phylogenetic tree building | — |

## Built-in Reference Database

- **46 HMM profiles** for protein-coding genes (multi-species MAFFT alignments)
- **46 protein reference FASTA** for BLAST fallback
- **323 gene products** with standardized naming
- **782 gene aliases** for cross-tool compatibility
- **23 known CMS genes** from 15+ plant species

## Citation

If you use MitoFlow in your research, please cite:

```
MitoFlow: A modern plant mitochondrial genome annotation and analysis platform.
```

## License

[MIT](LICENSE)
