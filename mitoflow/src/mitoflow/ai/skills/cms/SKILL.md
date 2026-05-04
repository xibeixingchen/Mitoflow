# Cytoplasmic Male Sterility (CMS) Detection Skill

## Contract

Detect and classify chimeric mitochondrial ORFs that may cause cytoplasmic male
sterility. Input is an annotated mitochondrial genome. Output is a ranked list
of candidate CMS-associated ORFs with confidence scores.

## Workflow

1. **Extract novel ORFs**: Scan for ORFs not matching known PCGs
2. **Chimera detection**: BLAST against known mitochondrial gene fragments
3. **Homology search**: Compare against curated CMS database
4. **ML-based scoring**: Random Forest classifier with chimera/homology/context features
5. **PPR binding site prediction**: Check for restorer-of-fertility targets
6. **Report**: Ranked candidates with evidence summary

## CMS Systems Reference

| CMS Type | Crop | Causal ORF | Origin |
|----------|------|------------|--------|
| WA-CMS | Rice | orf288 | Recombination |
| BT-CMS | Rice | orf79 | atp6-orf79 fusion |
| HL-CMS | Rice | orfH79 | atp6-orfH79 |
| CMS-HL | Maize | T-urf13 | Recombination |
| Pol-CMS | Wheat | orf256 | Recombination |

## ML Features

| Feature | Description |
|---------|-------------|
| ORF length | Novel ORFs typically 200–900 bp |
| Chimera score | Homology to multiple gene fragments |
| Upstream context | Promoter-like sequences |
| PPR binding | HMM search for PPR recognition motifs |
| Codon usage | Matches mitochondrial codon bias |

## Command Template

```bash
mitoflow cms -i genome.fasta -o cms_results/
```

## Key Criteria for Validation

1. Expression confirmed by RNA-seq (if available)
2. Associated with male-sterile phenotype
3. Not present in fertile maintainer lines
4. Restored by known Rf genes

## References

- Chen et al. (2019) Mol Plant — CMS overview (10.1016/j.molp.2019.09.004)
- "CMS in plants" (2021) Plant Cell (10.1093/plcell/koab123)
