# Evolutionary Rate Covariation (ERC) Skill

## Contract

Detect correlated evolutionary rates between mitochondrial and nuclear genes,
indicating functional coevolution. Input is annotated proteomes (multiple species).
Output is ERC correlation matrix and coevolution networks.

## Workflow

1. **Orthogroup inference**: OrthoFinder on proteomes
2. **Sequence alignment**: MAFFT for each orthogroup
3. **Gene tree inference**: IQ-TREE for each alignment
4. **Branch length reconciliation**: DLCpar or Treerecs
5. **ERC computation**: Correlate branch lengths across the species tree
6. **Statistical testing**: Permutation test + BH FDR correction
7. **Network analysis**: Build ERC network, detect communities

## Command Templates

```bash
# 1. OrthoFinder
orthofinder -f proteomes/ -t 8

# 2. MAFFT alignment (per OG)
mafft --auto og_sequences.fa > og_aligned.fa

# 3. IQ-TREE
iqtree3 -s og_aligned.fa -m MFP -B 1000 --prefix og_tree

# 4. ERC computation
ERCnet2 -t species_tree.nwk -d gene_trees/ -o erc_results/
```

## Key Parameters

| Param | Recommendation |
|-------|---------------|
| Alignment method | MAFFT --auto |
| Tree model | IQ-TREE ModelFinder |
| ERC method | Branch-by-branch (BXB) — most sensitive |
| FDR threshold | 0.05 (Benjamini-Hochberg) |

## Interpretation

- ERC > 0.5 + FDR < 0.05: Strong coevolution signal
- Network modularity: Functional modules (e.g., Complex I genes coevolve)
- Organelle-nuclear pairs: Key candidates for further validation

## References

- Forsythe et al. (2021) Mol Biol Evol — Plastid-nuclear coevolution (10.1093/molbev/msab123)
- ERCnet2 (2022) Bioinformatics — Genome-wide ERC (10.1093/bioinformatics/btac696)
