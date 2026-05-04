---
title: Plant Organelle Comparative Genomics
tags: comparative_genomics, synteny, gene_content, pan_genome
entities: OrthoFinder, synteny, pan_genome
references: ref_008
---

# Plant Organelle Comparative Genomics

## Approaches

### Gene Content Comparison
- Presence/absence of genes across species
- Gene family expansion/contraction
- Core vs accessory gene sets

### Synteny Analysis
- Gene order conservation
- Rearrangement detection
- Inversion and translocation events

### Pan-genome Analysis
- Core genome: genes present in all species
- Accessory genome: genes in some species
- Unique genome: species-specific genes

## Tools

| Tool | Function | Input |
|------|----------|-------|
| **OrthoFinder** | Orthogroup inference | Proteomes |
| **MCScanX** | Synteny detection | GFF + sequences |
| **MitoFlow synteny** | Gene order comparison | GenBank files |

## Key Observations

### Gene Order
- Highly variable across plant families
- Conserved within some genera
- Inversions are common

### Gene Content
- Core set: ~24 protein-coding genes conserved across land plants
- Variable genes: rps genes (some lost to nucleus)
- Species-specific: some ORFs, CMS-associated genes

### Genome Size
- Varies dramatically: 200kb to >10Mb
- Correlated with repeat content
- Not correlated with gene number

## Analysis Workflow

1. **Annotate** genomes with MitoFlow
2. **Cluster** genes with OrthoFinder
3. **Compare** gene content across species
4. **Detect** synteny with MitoFlow synteny
5. **Visualize** with MitoFlow viz

## References

- Emms & Kelly (2019) NAR — OrthoFinder
