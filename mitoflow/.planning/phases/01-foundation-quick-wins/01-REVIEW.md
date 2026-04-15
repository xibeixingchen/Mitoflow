---
phase: 01-foundation-quick-wins
reviewed: 2026-04-14T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - scripts/validate_against_gold_standard.py
  - src/mitoflow/annotate/pcg.py
  - src/mitoflow/models/genome.py
  - tests/test_circular_coords.py
findings:
  critical: 2
  warning: 6
  info: 3
  total: 11
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-14
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Review focused on circular coordinate math, tblastn boundary refinement, multi-exon gene handling, and gold-standard validation logic. Found several issues where circular genome semantics are not fully respected — particularly in trans-spliced gene merging, sequence extraction, and span calculations. The validation script also has methodological limitations in how it classifies splice-site (C) errors and compares multi-exon genes.

## Critical Issues

### CR-01: Trans-spliced gene merging uses linear gap, breaking origin-crossing exons

**File:** `src/mitoflow/annotate/pcg.py:1618`
**Issue:** `_merge_same_gene_annotations` computes inter-exon gap with linear arithmetic:
```python
gap = ann.genomic_start - prev.genomic_end - 1
```
On a circular genome, if one exon cluster is near the end (e.g., 499900) and another is near the beginning (e.g., 100), this yields a huge negative gap and splits the gene into two separate annotations. Plant mitochondrial trans-spliced genes can legitimately span the origin.
**Fix:** Pass `genome` into the function and use circular distance:
```python
gap = genome.circular_distance(ann.genomic_start, prev.genomic_end) - 1
```

### CR-02: Trans-spliced span validation uses linear distance, causing false rejection

**File:** `src/mitoflow/annotate/trans_splicing.py:866-867`
**Issue:** `annotate_trans_spliced_genes` checks whether to discard an HMM result using:
```python
hmm_span = abs(current.genomic_end - current.genomic_start)
```
For a gene crossing the origin (e.g., start=499900, end=100), this reports a span of ~499800 bp instead of the true circular span of ~200 bp, causing valid annotations to be discarded.
**Fix:** Use the circular span method:
```python
hmm_span = genome.circular_span(current.genomic_start, current.genomic_end)
```
The same pattern exists in `src/mitoflow/annotate/pcg.py:241` (`_validate_gene_span`), which should also be updated.

## Warnings

### WR-01: `subsequence` and `get_sequence_for_range` do not handle circular wrapping

**File:** `src/mitoflow/models/genome.py:72-84`
**Issue:** `subsequence(start, end)` uses plain Python slicing:
```python
return self.sequence[start - 1 : end]
```
If `start > end` (gene crosses the origin), it returns an empty or truncated string instead of the wrapped sequence. `get_sequence_for_range` delegates to `subsequence`, so it inherits the bug. While current callers mostly keep `start <= end` for individual exons, the API is inconsistent with `circular_span`, which explicitly supports `start > end`.
**Fix:**
```python
def subsequence(self, start: int, end: int) -> str:
    if end >= start:
        return self.sequence[start - 1 : end]
    return self.sequence[start - 1 :] + self.sequence[:end]
```

### WR-02: Boundary refinement functions miss start/stop codons across the origin

**File:** `src/mitoflow/annotate/pcg.py:869-983` and `1395-1543`
**Issue:** Both `_refine_boundaries` and `_refine_single_conservative` clamp coordinate searches to `[1, genome.length]` using `>= 1` and `<= genome.length` checks. They never wrap around the origin. A start codon just before the origin (e.g., positions 499998-500000) will be missed if the HMM hit starts near position 1.
**Fix:** Use `genome.wrap_position()` when advancing coordinates, or extract sequence with wrapping logic before scanning codons.

### WR-03: Validation script misclassifies C-errors (splice site) using overall position diff

**File:** `scripts/validate_against_gold_standard.py:259-261`
**Issue:** C-errors (splice site accuracy) are counted with:
```python
c_errors = len([d for d in position_diffs
                if d['max_diff'] > 10
                and not d['has_pmga_correction']])
```
This conflates any gene with an overall position offset >10 bp as a splice-site error, even for single-exon genes. It does not compare individual exon boundaries.
**Fix:** For multi-exon genes, compare exon start/end positions pairwise between NCBI and MitoFlow. Only count a C-error when an exon boundary differs by >10 bp.

### WR-04: Validation script only compares first CDS feature per gene

**File:** `scripts/validate_against_gold_standard.py:158-160`
**Issue:** `compare_gene_positions` uses `ncbi_pos[gene][0]` and `mito_pos[gene][0]`. If a GenBank contains multiple CDS features for a gene (e.g., separate exon records), only the first is compared. This can give misleading position diffs for multi-exon or duplicated annotations.
**Fix:** Compare the merged overall span or iterate all CDS features and match the closest corresponding feature.

### WR-05: `circular_positions_between` does not validate out-of-range inputs

**File:** `src/mitoflow/models/genome.py:59-70`
**Issue:** If `start` is 0 or negative, the method appends the invalid value to the result list before the safety break can fire:
```python
pos = start
while True:
    positions.append(pos)
    ...
    pos = (pos % self.length) + 1
```
**Fix:** Normalize inputs at the top of the method:
```python
start = self.wrap_position(start)
end = self.wrap_position(end)
```

### WR-06: `refine_exon_boundaries_with_codons` cannot find stop codons across the origin

**File:** `src/mitoflow/annotate/trans_splicing.py:780-786`
**Issue:** The function extracts downstream sequence with plain slicing:
```python
region = genome.sequence[exon.end:region_end]
```
If `region_end` exceeds `genome.length`, Python slicing silently truncates at the string end, missing any stop codon that wraps to the beginning of the genome.
**Fix:** Use a wrapping-aware sequence extraction helper (e.g., `genome.get_sequence_for_range` after fixing WR-01).

## Info

### IN-01: Dead code in `calculate_metrics`

**File:** `scripts/validate_against_gold_standard.py:215-218`
**Issue:** The `if (tp + fp + fn) > 0` guards on lines 215-218 are redundant because line 212 already handles the zero case.
**Fix:** Remove the redundant `else` branch or simplify the conditional structure.

### IN-02: Misleading function name `_blastn_fallback`

**File:** `src/mitoflow/annotate/pcg.py:571`
**Issue:** The function is named `_blastn_fallback` but it runs `tblastn` (protein vs translated nucleotide), not `blastn`.
**Fix:** Rename to `_tblastn_fallback` to match the actual tool invoked.

### IN-03: Missing test coverage for wrapping `subsequence` and invalid inputs

**File:** `tests/test_circular_coords.py`
**Issue:** Tests cover `circular_distance`, `circular_span`, `wrap_position`, and `circular_positions_between`, but do not test:
- `subsequence` / `get_sequence_for_range` with `start > end`
- `circular_positions_between` with out-of-range inputs (0, negative, > length)
**Fix:** Add tests for origin-crossing sequence extraction and boundary input validation.

---

_Reviewed: 2026-04-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
