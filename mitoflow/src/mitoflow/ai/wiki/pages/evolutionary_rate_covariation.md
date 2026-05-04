---
title: Evolutionary Rate Covariation (ERC) Analysis
tags: ERC, evolution, coevolution, phylogenetics
entities: ERC, ERCnet2, OrthoFinder
references: ref_007, ref_008, ref_010
---

# Evolutionary Rate Covariation (ERC) Analysis

## Overview

ERC detects correlated evolutionary rates between genes, indicating functional interaction or coevolution. Genes that interact functionally tend to evolve at correlated rates.

## Methods

### Branch-by-Branch (BXB)
- Correlates branch lengths for each gene pair across all branches of the species tree
- Most sensitive but requires accurate branch length estimation

### Root-to-Tip (R2T)
- Correlates root-to-tip distances for each gene pair
- Less sensitive but more robust to branch length estimation errors

### ERC2 Residual Method
- Computes regression residuals against a "master" branch length
- Controls for genome-wide rate variation
- Optional: sqrt/log transform, variance weighting

## Pipeline

1. **Orthogroup inference**: OrthoFinder on proteomes
2. **Gene tree inference**: IQ-TREE for each orthogroup
3. **Branch length reconciliation**: DLCpar or Treerecs
4. **ERC computation**: Correlate branch lengths
5. **Statistical testing**: Permutation test + BH FDR correction
6. **Network analysis**: Build ERC networks, community detection

## Tools

| Tool | Function | Reference |
|------|----------|-----------|
| **OrthoFinder** | Orthogroup inference | Emms & Kelly 2019 NAR |
| **ERCnet2** | ERC computation | Bioinformatics 2022 |
| **IQ-TREE** | Gene tree inference | Minh et al. 2020 NAR |
| **MAFFT** | Sequence alignment | Katoh & Standley 2022 |

## Applications

- **Organelle-nuclear coevolution**: Detect genes that coevolve between mitochondria/chloroplast and nucleus
- **Complex formation**: Identify genes encoding subunits of the same complex
- **Functional annotation**: Predict function based on coevolution patterns

## Key Findings

- Strongest ERC signals in proteostasis-related genes (Forsythe et al. 2021)
- Mitochondrial-nuclear coevolution detected across angiosperms
- Complex I subunits show coordinated evolution

## References

- Forsythe et al. (2021) Mol Biol Evol — Plastid-nuclear coevolution
- ERCnet2 (2022) Bioinformatics — Genome-wide ERC with gene duplication
