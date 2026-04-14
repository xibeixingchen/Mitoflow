# Architecture Research — MitoFlow Round 3

**Researched:** 2026-04-14

## Current Architecture Issues

### Issue 1: Mixed Concerns in pcg.py
`pcg.py` handles HMM search, filtering, AND boundary refinement. This makes it hard to tune individual aspects without side effects.

**Recommendation**: Don't refactor the file structure — it's working. Instead, make the tunable parameters (thresholds, rules) configurable rather than hardcoded.

### Issue 2: No Circular Coordinate Abstraction
Coordinate math is scattered — linear distance used everywhere. Need a centralized utility.

**Recommendation**: Add `circular_distance()` and `circular_span()` to `models/genome.py` on the `GenomeSequence` class. Then update call sites.

### Issue 3: FIXED_OFFSET_GENES Is Not Adaptive
Hardcoded offset table in boundary.py doesn't work across species. Some species don't have the offset, others have different magnitudes.

**Recommendation**: Replace with tblastn-based boundary refinement that adapts per species automatically. The tblastn alignment boundaries are species-specific by nature.

### Issue 4: Exon Merging Lacks Splice Site Validation
Current merging picks best BLAST hit per exon without checking splice site consensus. This causes C errors.

**Recommendation**: Add a splice site scoring step after BLAST-based exon selection. Check GT/AG at intron boundaries and penalize exons that violate consensus.

### Issue 5: Validation Script Uses Linear Distance
Position comparison in validation script doesn't handle circular genomes.

**Recommendation**: Add circular distance to validation comparison. This is separate from the annotation pipeline fix.

## Proposed Component Structure (for Round 3)

```
No structural changes needed — improvements are within existing modules:

models/genome.py
  + circular_distance(start, end, genome_length)
  + circular_span(start, end, genome_length)

annotate/pcg.py
  ~ Per-gene HMM score thresholds (PER_GENE_MIN_SCORES)
  ~ Improved duplicate filtering with gene copy rules

annotate/boundary.py
  ~ Remove FIXED_OFFSET_GENES
  ~ Adaptive boundary correction using tblastn alignment boundaries
  ~ Extend start codon search range for specific genes

annotate/trans_splicing.py
  ~ Fix nad4 36bp offset bug
  ~ Add splice site consensus check (GT/AG)
  ~ Circular coordinate support in exon merging

scripts/validate_against_gold_standard.py
  ~ Circular distance for position comparison
  ~ Weighted scoring (exclude poorly-annotated species from A-error)
```

## Build Order

1. **Circular coordinate utilities** (models/genome.py) — foundational
2. **Validation script fix** (scripts/) — quick win, shows immediate B-error improvement
3. **nad4 bug fix** (annotate/trans_splicing.py) — high-impact, isolated fix
4. **Per-gene thresholds** (annotate/pcg.py) — reduces A errors
5. **Adaptive boundary** (annotate/boundary.py) — replaces hardcoded offsets
6. **Splice site validation** (annotate/trans_splicing.py) — improves C errors

## Data Flow (Unchanged)

The annotation pipeline flow stays the same:
```
FASTA → HMM search → filtering → exon merging → boundary correction → CDS validation → output
```

Improvements are injected at each stage:
- HMM search: per-gene thresholds
- Filtering: gene copy rules, length validation
- Exon merging: circular coords, splice sites
- Boundary correction: adaptive (tblastn-based), not hardcoded
- Validation: circular distance, weighted scoring
