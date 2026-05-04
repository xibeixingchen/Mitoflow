---
title: RNA Editing in Plant Mitochondria
tags: RNA_editing, C_to_U, PPR_proteins, mitochondria
entities: RNA editing, PPR proteins
references: ref_006, ref_013
---

# RNA Editing in Plant Mitochondria

## Overview

C-to-U RNA editing is a post-transcriptional modification that is extensive in plant mitochondria. A typical plant mitochondrial genome has 400-1500 editing sites.

## Mechanism

### Types of Editing
1. **C-to-U conversion**: Most common (>99% of sites)
2. **U-to-C conversion**: Rare, found in some ferns and hornworts

### Editing Factors
- **PPR proteins**: Primary editing factors
- **MORF/RIP proteins**: Editing co-factors
- **ORRM proteins**: Organelle RNA recognition motif proteins

### Editing Sites
- Mostly in coding regions
- Often at first or second codon position
- Can create start codons (AUG from ACG)
- Can remove premature stop codons (UAA from CAA)

## Impact on Gene Expression

| Effect | Example | Consequence |
|--------|---------|-------------|
| Start codon creation | cox1, nad1, nad4L, rps10 | Protein translation initiation |
| Stop codon removal | ccmFC, rps10, atp9, atp6, rps11 | Full-length protein production |
| Amino acid change | Most sites | Protein function modification |

## Implications for Annotation

1. **Start codon prediction**: Must consider RNA editing
2. **Stop codon prediction**: Some genes have premature stops corrected by editing
3. **Phylogenetic analysis**: DNA-level vs protein-level trees differ
4. **Gene prediction**: HMM models should account for editing

## MitoFlow RNA Editing Module

MitoFlow includes:
- **C-to-U site prediction**: Based on flanking context and conservation
- **Protein correction**: Applies predicted edits to protein sequences
- **VCF/GenBank output**: Standard format for editing sites

## References

- "Targeted RNA editing in plant mitochondria" (2021) Nature Plants
- Chen et al. (2019) Mol Plant — RNA editing overview
