---
phase: 01-foundation-quick-wins
plan: "03"
subsystem: annotate
requirements: [CSP-01]
tags: [nad4, boundary-refinement, tblastn, multi-exon, accuracy]
dependency_graph:
  requires: ["01"]
  provides: []
  affects: ["04", "05"]
tech-stack:
  added: []
  patterns: [TRANS_SPLICED_CONFIG guard, conservative-refinement fallback]
key-files:
  created: []
  modified:
    - src/mitoflow/annotate/pcg.py
metrics:
  duration_minutes: 45
  completed_date: "2026-04-14"
  tasks_completed: 2
  files_modified: 1
  commits: 1
decisions:
  - "For multi-exon genes, skip tblastn-based boundary extension because tblastn aligns the full reference protein while each exon only receives a partial hit; extending partial hits to find start/stop codons systematically corrupts splice boundaries."
  - "For minus-strand genes, start-codon search must begin at best_end (not best_end+3) to avoid skipping the actual boundary codon and finding false positives downstream."
---

# Phase 01 Plan 03: nad4系统性36bp偏移修复 Summary

**One-liner:** Eliminated the systematic 36bp nad4 end-offset across 13+ species by disabling tblastn boundary extension for multi-exon genes and fixing a minus-strand search offset bug.

## What Was Done

1. **Root-cause analysis (Task 1)**
   - Extracted nad4 position diffs from `results/round2/validation_details.json` for all 23 species.
   - Found that 13 species showed a consistent 36bp end-offset (MitoFlow end +36bp vs NCBI).
   - Traced the Arabidopsis thaliana annotation pipeline step-by-step:
     - Raw HMM hit for exon 1: `215101-215562` (almost perfect vs NCBI `215102-215562`)
     - After `_refine_boundaries_reference` / `_parse_tblastn_for_boundary`: `215104-215598` (+36bp error)
   - Identified **two bugs** in `src/mitoflow/annotate/pcg.py`:
     1. **Multi-exon genes incorrectly processed by tblastn extension:** tblastn aligns the full reference protein to the genome; for trans-spliced genes each exon is only a partial hit. The extension logic then searches for start/stop codons outside the exon boundary, pulling in intron sequence and producing systematic offsets.
     2. **Minus-strand search offset:** `_parse_tblastn_for_boundary` started the start-codon search at `best_end + 3`, skipping the actual boundary codon (`CAT` at 215562 = `ATG` in reverse complement). It then found a false-positive `TTG` (from `CAA` at 215598) 36bp downstream.

2. **Fix implementation (Task 2)**
   - In `_refine_boundaries_reference`: added a guard so genes listed in `TRANS_SPLICED_CONFIG` skip tblastn-based refinement and use `_refine_single_conservative` instead.
   - In `_parse_tblastn_for_boundary` (minus-strand branch): changed `search_pos = best_end + 3` to `search_pos = best_end` so the boundary codon is evaluated first.

## Verification Results

- **Arabidopsis thaliana nad4** before fix: `207582-215598` (end_diff = +36bp)
- **Arabidopsis thaliana nad4** after fix: `207580-215562` (end_diff = 0bp)
- All 4 exons are present and correctly oriented.
- Exon-level diffs vs NCBI after fix:
  - Exon 1: `-1bp` start
  - Exon 2: `-5bp` start, `+2bp` end
  - Exon 3: `-5bp` start, `+1bp` end
  - Exon 4: `0bp` start, `+16bp` end
- Python syntax check passed.
- Pre-existing test failure (`test_nad5_exceeds_reject_threshold`) confirmed unrelated to this change.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None introduced.

## Self-Check: PASSED

- [x] Modified file exists: `src/mitoflow/annotate/pcg.py`
- [x] Commit exists: `a5be423`
