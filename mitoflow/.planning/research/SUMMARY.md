# Research Summary — MitoFlow Round 3

**Synthesized:** 2026-04-14

## Stack Key Findings

- **HMM thresholds must be per-gene**: Ribosomal proteins (rps/rpl) need min_score≥60; core PCG can use ≥40. Current blanket 30 is too permissive.
- **Circular coordinate math is critical**: Modular arithmetic for distance/span on circular genomes. Without it, multi-exon genes in large genomes show phantom large offsets.
- **nad4 has a specific bug**: 36bp offset = 12 codons — likely codon phase or exon boundary calculation error. Systematic across 15 species.

## Table Stakes (Must Fix)

1. **Circular genome coordinate handling** — affects B errors in validation AND C errors in exon merging
2. **Validation script circular distance** — quick win, many B errors are measurement artifacts
3. **nad4 36bp fix** — single bug, 15 species affected
4. **Per-gene HMM thresholds** — rps/rpl need higher stringency
5. **False positive filtering** — rps19/mttb/sdh4 are frequently mispredicted
6. **Gene length validation** — flag genes outside expected ranges

## Watch Out For

- **Don't over-filter**: Raising thresholds too high loses real genes — monitor sensitivity
- **False gold standards**: Some NCBI annotations have <10 genes — don't optimize for bad references
- **One change at a time**: Track per-species regressions after each modification
- **Circular math off-by-one**: Write unit tests before applying to pipeline
- **Splice site consensus not universal**: Plant mitochondrial introns include group II with non-canonical boundaries

## Recommended Phase Structure

### Phase 1: Foundation + Quick Wins
- Circular coordinate utilities in models/genome.py
- Validation script circular distance fix
- Per-gene HMM score thresholds
- nad4 bug investigation and fix

### Phase 2: A-Error Reduction
- Gene-specific false positive rules (rps19, mttb, sdh4)
- Gene length validation integration
- Improved duplicate filtering

### Phase 3: B/C-Error Deep Fixes
- Replace FIXED_OFFSET_GENES with adaptive tblastn boundaries
- Splice site consensus validation (GT/AG, with GC/AG alternative)
- Reading frame phase tracking across exons
