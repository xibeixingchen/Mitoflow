---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-04-15T14:00:00Z"
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 7
  completed_plans: 6
  percent: 86
---

# State: MitoFlow Round 3

**Initialized:** 2026-04-14
**Status:** Executing Phase 03

## Current Phase

**Phase 3: B/C Deep Fixes**

- Status: Code delivery complete; validation complete
- Plan: `.planning/phases/03-bc-deep-fixes/03-PLAN.md`
- Next step: Review Phase 3 results and decide whether to iterate further on B/C errors or move to release

## Phase History

### Phase 1: Foundation + Quick Wins

- Status: Completed (code delivery)
- Verification: 8/10 truths verified; gaps accepted as measurement/validation pending
- Key commits: circular coords (861c55d), validation fix (edf4517/45fb4cd), nad4 fix (a5be423)
- Deliverables: `circular_distance`/`circular_span`, `validate_against_gold_standard.py` circular baseline, nad4 systematic offset fix

### Phase 2: A-Error Reduction

- Status: Completed
- Key finding: `validate_against_gold_standard.py` only read the first GenBank file for multi-accession species, inflating baseline A-errors by ~140+
- Corrected baseline (Round 2 circular, multi-accession fixed): F1=90.93%, A-errors=302
- Phase 2 changes achieved: F1=91.72%, A-errors=292, rps19 FP reduced from 12→1 species
- All 130 unit tests pass

### Phase 3: B/C Deep Fixes

- Status: Code delivery and validation complete
- Key commits: circular boundary start/stop search (a269a20), splice-site consensus scoring (a269a20), phase tracking micro-adjustment (4cd9958), adaptive tblastn refinement (7662413), fixed offset cox2 guard (48140fb)
- Deliverables:
  - `src/mitoflow/models/genome.py`: circular `subsequence()` origin-crossing support
  - `src/mitoflow/annotate/boundary.py`: circular-aware start/stop search, `_restore_phase_continuity()`, `_refine_boundary_by_tblastn()`, fixed offset guard
  - `src/mitoflow/annotate/trans_splicing.py`: splice-site consensus scoring (`_score_splice_sites()`), exon reference directory fix, cox2 exon fragment merge
  - `src/mitoflow/models/gene.py`: `ExonRecord.phase` field
- Validation: 28 species, F1=91.72%, B-errors=271, C-errors=408

## Milestone Progress

| Phase | Status | F1 Target |
|-------|--------|-----------|
| Phase 1: Foundation + Quick Wins | Completed | ≥83% |
| Phase 2: A-Error Reduction | Completed | ≥87% |
| Phase 3: B/C Deep Fixes | Completed (code delivery) | ≥90% |

## Key Metrics

### Original (Buggy) Baseline

| Metric | Value |
|--------|-------|
| Accuracy | 71.86% |
| Sensitivity | 92.94% |
| F1 | 79.51% |
| Exact match (<50bp) | 66.0% |
| A errors | 444 |
| B errors | 259 |
| C errors | 414 |

### Corrected Baseline (multi-accession validation fix)

| Metric | Value |
|--------|-------|
| Accuracy | 86.01% |
| Sensitivity | 92.84% |
| F1 | 90.93% |
| A errors | 302 |
| B errors | 299 |
| C errors | 456 |

### Phase 2 Results

| Metric | Value | Δ vs Corrected Baseline |
|--------|-------|------------------------|
| Accuracy | 87.33% | +1.32 pp |
| Sensitivity | 93.12% | +0.28 pp |
| F1 | 91.72% | +0.79 pp |
| A errors | 292 | −10 |
| B errors | 283 | −16 |
| C errors | 414 | −42 |

### Phase 3 Results

| Metric | Value | Δ vs Phase 2 |
|--------|-------|--------------|
| Accuracy | 87.78% | +0.45 pp |
| Sensitivity | 93.31% | +0.19 pp |
| F1 | 91.72% | +0.00 pp |
| A errors | 292 | 0 |
| B errors | 271 | −12 |
| C errors | 408 | −6 |
| High-F1 species (≥98%) | 8 | maintained |

## Phase 3 Success Criteria Assessment

| Criterion | Target | Actual | Status | Notes |
|-----------|--------|--------|--------|-------|
| B-error | <100 | 271 | ❌ Not met | Reduced by 12; large-genome species (Camellia 31, Nymphaea 16) remain dominant contributors |
| C-error | <150 | 408 | ❌ Not met | Reduced by 6; target was extremely aggressive |
| FIXED_OFFSET_GENES usage | <5 species | TBD | ⚠️ Partial | tblastn refinement now skips fixed offset when successful; need log analysis |
| Splice-site consensus coverage | all multi-exon | yes | ✅ Met | `_score_splice_sites()` integrated into `merge_exons_to_gene` |
| F1 | ≥90% | 91.72% | ✅ Met | Held steady with no regression |
| High-F1 species no regression | ≥98% | yes | ✅ Met | Ipomoea/Solanum/Punica all at 100% F1 |
| Unit tests pass | all | all | ✅ Met | 130+ tests pass |

## Key Deliverables

- `src/mitoflow/annotate/pcg.py`: per-gene HMM thresholds (`PER_GENE_MIN_SCORES`), presence-based filters, length validation, improved duplicate filtering (`_filter_duplicates`)
- `src/mitoflow/annotate/trans_splicing.py`: circular coordinate support (`_circular_gene_span`), splice-site consensus scoring, cox2 exon reference fix
- `src/mitoflow/annotate/boundary.py`: circular-aware start/stop search, phase continuity micro-adjustment, adaptive tblastn refinement, fixed offset guard
- `src/mitoflow/models/genome.py`: circular `subsequence()` origin-crossing support
- `src/mitoflow/models/gene.py`: `ExonRecord.phase` field
- `scripts/validate_against_gold_standard.py`: multi-accession GenBank merge fix

## Session Log

| Date | Event |
|------|-------|
| 2026-04-14 | Project initialized, codebase mapped, research done, roadmap created, Phase 1 completed |
| 2026-04-15 | Entered Phase 2: A-Error Reduction |
| 2026-04-15 | Completed Wave 1 & 2 implementation; discovered and fixed validation multi-accession bug; full 27-species batch run complete |
| 2026-04-15 | Entered Phase 3: B/C Deep Fixes; completed circular boundary, splice-site scoring, phase tracking, and adaptive tblastn refinement |
