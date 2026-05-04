# Assembly Skill

## Contract

Assemble plant organelle genomes from raw sequencing reads using seed-and-extend
or reference-guided methods. Input is paired-end FASTQ. Output is a circular
consensus sequence in FASTA format with assembly statistics.

## Workflow

1. **Quality check** raw reads with FastQC
2. **Trim adapters** with fastp or Trimmomatic
3. **Seed-based assembly** with GetOrganelle (recommended default)
4. **Alternative**: NOVOPlasty for seed-based, MITObim for reference-guided
5. **Validate** circularity and coverage

## Tools

| Tool | Command Template |
|------|-----------------|
| GetOrganelle | `get_organelle_reads.py -1 R1.fq.gz -2 R2.fq.gz -o out/ -F mitochondria -t 8 -k 21,45,65,85,105` |
| NOVOPlasty | `NOVOPlasty.pl -c config.txt` |
| MITObim | `MITObim.pl -start seed.fa -readpool reads.fq -ref ref.fa --quick` |

## Parameters

- `--seed-gene`: cox1 / rps11 / atp6 (mitochondria)
- `--kmer-range`: 21–121 (GetOrganelle), adjust for genome size
- `--threads`: 4–16

## Quality Checks

- Circularity: ends overlap by ≥ 50 bp with ≥ 99% identity
- Coverage: 100–1000x expected for organelle reads
- Completeness: BUSCO assessment against embryophyta_odb10

## References

- Jin et al. (2020) Genome Biol — GetOrganelle (10.1093/nar/gkz940)
- Dierckxsens et al. (2017) Genome Biol — NOVOPlasty (10.1186/s13059-017-1187-4)
- Hahn et al. (2013) BMC Genomics — MITObim (10.1186/1471-2164-14-757)
