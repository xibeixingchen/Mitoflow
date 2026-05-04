# Annotation Skill

## Contract

Annotate plant mitochondrial genomes with protein-coding genes, tRNAs, rRNAs,
and structural features. Input is a FASTA genome sequence. Output is GFF3,
GenBank, and FASTA files for all annotated features.

## Workflow

1. **Protein-coding genes**: HMM search (46 profiles) + BLAST validation
2. **tRNA genes**: tRNAscan-SE + ARAGORN dual prediction
3. **rRNA genes**: Barrnap + BLAST validation
4. **Boundary correction**: Start/stop codon refinement
5. **RNA editing prediction**: C-to-U sites based on flanking context
6. **QC assessment**: Five-dimensional quality check

## Command Template

```bash
mitoflow annotate -i genome.fasta -o results/ --name Sample --threads 8
```

## Key Parameters

| Param | Default | Description |
|-------|---------|-------------|
| `--threads` | 4 | Parallel workers |
| `--skip-trna` | false | Skip tRNA prediction |
| `--skip-rrna` | false | Skip rRNA prediction |
| `--skip-qc` | false | Skip quality checks |

## Gene Start/Stop Rules

- **Standard start**: ATG (check for ACG if RNA-edited)
- **Standard stop**: TAA, TAG, TGA
- **Trans-spliced genes**: nad1, nad2, nad3, nad4, nad5, nad6, rps10
- **Start-gain editing**: cox1, nad1, nad4L, rps10 (in some species)

## Output Files

| Directory | Contents |
|-----------|----------|
| `gff/` | GFF3 annotation |
| `genbank/` | GenBank flat file |
| `fasta/` | CDS, protein, tRNA, rRNA sequences |
| `report/` | QC reports and statistics |

## References

- PyHMMER + BLAST+ for gene detection
- tRNAscan-SE: Lowe & Eddy (2016) NAR
