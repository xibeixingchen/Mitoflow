---
title: Trans-splicing in Plant Mitochondria
tags: trans_splicing, intron, nad, mitochondria, rps10
entities: trans-splicing, nad1, nad2, nad3, nad4, nad5, nad6, rps10
references: ref_006, ref_013
---

# Trans-splicing in Plant Mitochondria

## Overview

Trans-splicing is a process where exons of a gene are located on different genomic loci and must be joined post-transcriptionally. In plant mitochondria, several complex I (NADH dehydrogenase) subunit genes require trans-splicing.

## Trans-spliced Genes

| Gene | Exons | Complex | Notes |
|------|-------|---------|-------|
| **nad1** | 5 exons | Complex I | 3 trans-splicing events |
| **nad2** | 5 exons | Complex I | 2 trans-splicing events |
| **nad3** | 2 exons | Complex I | 1 trans-splicing event |
| **nad4** | 4 exons | Complex I | 2 trans-splicing events |
| **nad5** | 5 exons | Complex I | 3 trans-splicing events |
| **nad6** | 2 exons | Complex I | 1 trans-splicing event |
| **rps10** | 2-3 exons | Ribosome | 1 trans-splicing event |

## Mechanism

### Group II Intron Trans-splicing
- Most trans-splicing in plant mitochondria involves **group II introns**
- Intron fragments are located at separate genomic loci
- RNA molecules base-pair to form functional intron structures
- Splicing proceeds via the same mechanism as cis-splicing

### Recognition Elements
- Exon sequences flanking the splice sites
- Intron secondary structure (domains I-VI)
- Nuclear-encoded splicing factors (maturases)

## Implications for Annotation

1. **Gene prediction**: Exons may be on different strands or distant loci
2. **Boundary detection**: Each exon boundary must be independently verified
3. **Protein prediction**: Full protein requires correct exon joining
4. **Phylogenetics**: DNA-level analysis must account for exon separation

## MitoFlow Handling

MitoFlow's annotation pipeline:
- Detects trans-spliced genes by searching for individual exons
- Uses reference exon sequences from `blast_refs/exons/`
- Joins exons in correct order based on reference alignment
- Reports exon coordinates separately in GFF output

## References

- "Trans-splicing of plant mitochondrial genes" (2018) Plant Cell
- Chen et al. (2019) Mol Plant — mitochondrial gene expression
