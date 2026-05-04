# Comparative Genomics Skill

## Contract

Compare plant mitochondrial genomes across species to detect gene content
variation, synteny blocks, rearrangements, and pan-genome patterns.
Input is annotated GenBank files. Output is comparative analysis tables and
visualization plots.

## Workflow

1. **Gene content comparison**: Presence/absence matrix across species
2. **Orthogroup inference**: OrthoFinder on annotated proteomes
3. **Synteny detection**: MCScanX or MitoFlow synteny
4. **Rearrangement analysis**: Inversions, translocations, gene losses
5. **Pan-genome analysis**: Core/accessory/unique gene sets
6. **Visualization**: Circos plots, synteny maps

## Command Templates

```bash
# Gene content comparison
mitoflow pi -i genbank_dir/ -o diversity_results/

# Synteny detection
mitoflow synteny -i genbank_dir/ -o synteny_results/

# Phylogenetic tree
mitoflow phylo -i aligned_seqs/ -o phylo_results/
```

## Key Metrics

| Metric | Description |
|--------|-------------|
| Gene content Jaccard | Overlap between species pairs |
| Synteny score | Conserved gene blocks ÷ total genes |
| Rearrangement distance | Inversion/translocation count |
| Core genome size | Genes present in all species |
| Pan-genome size | Total unique genes across all species |

## Gene Content Categories

- **Core**: ~24 PCGs conserved across land plants
- **Variable**: rps genes (some transferred to nucleus)
- **Species-specific**: Novel ORFs, CMS-associated genes

## Genome Size Patterns

- Angiosperms: 200 kb – 11.3 Mb (Silene)
- Gymnosperms: 1–2 Mb (relatively conserved)
- Size correlated with repeat content, not gene number

## Visualization

- **Circos**: Circular genome maps with gene density, GC, repeats
- **Synteny maps**: Linear genome alignments across species
- **Phylogenetic tree**: With gene content annotation

## References

- Emms & Kelly (2019) NAR — OrthoFinder (10.1093/nar/gky1080)
- Chen et al. (2019) Mol Plant — Comparative mitochondrial genomics
