---
title: Organelle Genome Assembly Tools
tags: assembly, tools, mitochondria, chloroplast
entities: GetOrganelle, NOVOPlasty, MITObim, PGA
references: ref_001, ref_002, ref_003, ref_004
---

# Organelle Genome Assembly Tools

## Comparison Table

| Tool | Method | Input | Reference |
|------|--------|-------|-----------|
| **GetOrganelle** | Seed-and-extend | Illumina/long reads | Jin et al. 2020 Genome Biol |
| **NOVOPlasty** | Seed-based | Illumina/Ion Torrent | Dierckxsens et al. 2017 Genome Biol |
| **MITObim** | Reference-guided | Short reads + ref | Hahn et al. 2013 BMC Genomics |
| **PGA** | Integrated | WGS reads | Qu et al. 2022 NAR |
| **IOGA** | Iterative | Illumina | Jian et al. 2022 |
| **TOGA** | Reference-free | Long reads | Sheng et al. 2024 |

## GetOrganelle
- **DOI**: 10.1093/nar/gkz940
- **Method**: Extracts organelle reads using k-mer baiting, then assembles with SPAdes
- **Strengths**: Fast, accurate, supports both mitochondria and chloroplast
- **Best for**: Most plant species with Illumina data

## NOVOPlasty
- **DOI**: 10.1186/s13059-017-1187-4
- **Method**: Seed-based assembly from a conserved gene
- **Strengths**: Simple, works with various data types
- **Best for**: Chloroplast genomes, smaller mitochondrial genomes

## MITObim
- **DOI**: 10.1186/1471-2164-14-757
- **Method**: Iterative baiting and mapping against reference
- **Strengths**: Works with distant references, good for degraded DNA
- **Best for**: Ancient DNA, low-coverage samples

## PGA
- **DOI**: 10.1093/nar/gac387
- **Method**: Integrated assembly and annotation
- **Strengths**: Complete pipeline from reads to annotation
- **Best for**: Users wanting a one-stop solution

## Recommendations

1. **Default choice**: GetOrganelle — most versatile and accurate
2. **Long reads available**: Use GetOrganelle with long-read mode
3. **Degraded samples**: MITObim with available reference
4. **Chloroplast focus**: NOVOPlasty or GetOrganelle
5. **Full pipeline**: PGA for assembly + annotation
