---
title: Cytoplasmic Male Sterility (CMS) in Plants
tags: CMS, male_sterility, hybrid, mitochondria, Rf_genes
entities: CMS, Rf genes, orf288, orf79
references: ref_006, ref_012
---

# Cytoplasmic Male Sterility (CMS)

## Overview

CMS is a maternally inherited inability to produce functional pollen, caused by chimeric mitochondrial genes. It is widely used in hybrid seed production.

## Mechanism

### CMS-causing Genes
CMS is typically caused by novel open reading frames (ORFs) created by:
- Recombination between mitochondrial genes
- Fusion of gene fragments
- Insertion of foreign sequences

| CMS Type | Crop | Causal ORF | Origin |
|----------|------|------------|--------|
| WA-CMS | Rice | orf288 | Recombination |
| BT-CMS | Rice | orf79 | atp6-orf79 fusion |
| HL-CMS | Rice | orfH79 | atp6-orfH79 |
| CMS-HL | Maize | T-urf13 | Recombination |
| Pol-CMS | Wheat | orf256 | Recombination |

### Restorer-of-Fertility (Rf) Genes
- Nuclear genes that suppress CMS
- Most encode PPR (pentatricopeptide repeat) proteins
- Act post-transcriptionally to degrade CMS-associated transcripts
- Some act by editing RNA

## CMS in MitoFlow

MitoFlow includes a CMS prediction module:
- **ML-based scoring**: Random Forest classifier
- **Features**: chimera detection, homology search, PPR binding sites
- **Reference database**: curated CMS-associated sequences

## Applications

1. **Hybrid seed production**: CMS eliminates need for hand emasculation
2. **Three-line system**: CMS line + maintainer line + restorer line
3. **Two-line system**: Environment-sensitive male sterility

## References

- Chen et al. (2019) Mol Plant — Plant mitochondrial genome evolution and CMS
- "Cytoplasmic male sterility in plants" (2021) Plant Cell
