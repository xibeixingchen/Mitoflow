---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-04-15T10:30:00Z"
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 7
  completed_plans: 4
  percent: 57
---

# State: MitoFlow Round 3

**Initialized:** 2026-04-14
**Status:** Executing Phase 02

## Current Phase

**Phase 2: A-Error Reduction**

- Status: In progress; Wave 1 & Wave 2 code delivery complete
- Plan: `.planning/phases/02-a-error-reduction/02-PLAN.md`
- Next step: Verify and finalize Phase 2; decide whether to proceed to Phase 3 or address Capsicum/Glycine ORF gaps

## Phase History

### Phase 1: Foundation + Quick Wins

- Status: Completed (code delivery)
- Verification: 8/10 truths verified; gaps accepted as measurement/validation pending
- Key commits: circular coords (861c55d), validation fix (edf4517/45fb4cd), nad4 fix (a5be423)
- Deliverables: `circular_distance`/`circular_span`, `validate_against_gold_standard.py` circular baseline, nad4 systematic offset fix

### Phase 2: A-Error Reduction

- Status: Code delivery complete; validation revealed critical baseline measurement bug
- Key finding: `validate_against_gold_standard.py` only read the first GenBank file for multi-accession species, inflating baseline A-errors by ~140+
- Corrected baseline (Round 2 circular, multi-accession fixed): F1=90.93%, A-errors=302
- Phase 2 changes achieved: F1=91.72%, A-errors=292, rps19 FP reduced from 12→1 species
- All 130 unit tests pass

## Milestone Progress

| Phase | Status | F1 Target |
|-------|--------|-----------|
| Phase 1: Foundation + Quick Wins | Completed | ≥83% |
| Phase 2: A-Error Reduction | In progress (code complete) | ≥87% |
| Phase 3: B/C Deep Fixes | Not started | ≥90% |

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

### Phase 2 Results (current code)

| Metric | Value | Δ vs Corrected Baseline |
|--------|-------|------------------------|
| Accuracy | 87.33% | +1.32 pp |
| Sensitivity | 93.12% | +0.28 pp |
| F1 | 91.72% | +0.79 pp |
| A errors | 292 | −10 |
| B errors | 283 | −16 |
| C errors | 414 | −42 |

## Phase 2 Success Criteria Assessment

| Criterion | Status | Notes |
|-----------|--------|-------|
| A-error < 200 | ❌ Partial | 292; blocked by Capsicum (152) and Glycine max (65) ORF false negatives |
| Sensitivity ≥ 92% | ✅ Met | 93.12% |
| rps19 FP < 3 species | ✅ Met | Reduced from 12 → 1 species |
| F1 ≥ 87% | ✅ Met | 91.72% |
| Low-F1 species +10 pp | ❌ Partial | Glycine max +0.39 pp; Capsicum unchanged. Requires ORF prediction, out of Phase 2 scope |
| Unit tests pass | ✅ Met | 130 passed, 1 skipped |
| High-F1 species no regression | ✅ Met | Ipomoea/Solanum/Punica all at 100% F1 |

## Key Deliverables

- `src/mitoflow/annotate/pcg.py`: per-gene HMM thresholds (`PER_GENE_MIN_SCORES`), presence-based filters, length validation, improved duplicate filtering (`_filter_duplicates`)
- `src/mitoflow/annotate/trans_splicing.py`: circular coordinate support (`_circular_gene_span`)
- `scripts/validate_against_gold_standard.py`: multi-accession GenBank merge fix
- `tests/test_trans_splicing.py`: `_circular_gene_span` regression tests

## Session Log

| Date | Event |
|------|-------|
| 2026-04-14 | Project initialized, codebase mapped, research done, roadmap created, Phase 1 completed |
| 2026-04-15 | Entered Phase 2: A-Error Reduction |
| 2026-04-15 | Completed Wave 1 & 2 implementation; discovered and fixed validation multi-accession bug; full 27-species batch run complete |
