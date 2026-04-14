# Integrations — MitoFlow

**Mapped:** 2026-04-14

## External Bioinformatics Tools

All external tools are invoked via `subprocess` (no Python bindings). Tools must be in `$PATH`.

### Annotation Pipeline

1. **pyhmmer** (Python library) — HMM search for protein-coding genes (primary method)
2. **BLAST+ (tblastn)** — Protein-to-genome alignment for gene boundary refinement and PCG backup
3. **tRNAscan-SE** — tRNA gene prediction (primary tRNA tool)
4. **ARAGORN** — tRNA gene prediction (secondary/backup)
5. **Barrnap** — rRNA gene prediction

### Quality Control

6. **minimap2** — Read mapping for coverage analysis
7. **samtools** — BAM file processing, coverage stats

### Comparative Analysis

8. **MAFFT** — Multiple sequence alignment (for phylo, synteny)
9. **trimAl** — Alignment trimming
10. **iqtree2/iqtree** — Phylogenetic tree construction
11. **KaKs_Calculator-3.0** — Ka/Ks selection pressure calculation
12. **blastn** — Repeat detection, NUMT detection, MTPT detection

### Visualization

13. **Rscript** — R-based visualization (OGDrawR, and *_r.py modules for various analyses)
14. **gbdraw** (Python) — Circular genome visualization
15. **pycirclize** (Python) — Circular plots
16. **pygenomeviz** (Python) — Linear genome/synteny plots

## Data Inputs

| Input Type | Format | Command |
|------------|--------|---------|
| Mitochondrial genome | FASTA | `annotate`, `qc`, `gc`, `repeat`, `multiconf` |
| GenBank annotation | `.gb` | `viz`, `report`, `rna_edit`, `codon`, `cms`, `phylo`, `synteny` |
| Chloroplast genome | FASTA | `mtpt`, `qc --cp` |
| Nuclear genome | FASTA | `numt --nuc` |
| BAM alignment | `.bam` | `qc --bam` |
| GFA assembly graph | `.gfa` | `qc --gfa` |
| Long reads | FASTQ | `multiconf --reads` |

## Data Outputs

| Output Type | Format | Location |
|-------------|--------|----------|
| Gene annotations | GFF3 | `{output}/gff/{name}.gff` |
| Annotated genome | GenBank | `{output}/genbank/{name}.gb` |
| Extracted sequences | FASTA | `{output}/fasta/` (CDS, Protein, tRNA, rRNA, intron, Gene) |
| QC reports | JSON + TXT | `{output}/report/` |
| QC plots | PNG/SVG/PDF | `{output}/report/` |
| HTML report | HTML | `{output}/report/{name}_report.html` |
| MTPT report | TXT | `{output}/report/{name}_mtpt.txt` |
| Codon tables | TSV | `{output}/report/` |
| Ka/Ks results | TSV | `{output}/report/` |
| Phylo alignment | FASTA/PHYLIP | `{output_dir}/` |
| Phylo tree | Newick | `{output_dir}/phylo.treefile` |

## No Network/API Integrations

MitoFlow is entirely offline — no web APIs, no databases to connect to. All reference data is bundled in `src/mitoflow/data/`.
