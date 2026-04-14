---
phase: 01-foundation-quick-wins
plan: 01
subsystem: core

tags: [circular-genome, coordinates, pydantic, pytest]

requires: []
provides:
  - Circular coordinate utilities on GenomeSequence
  - Unit test suite for circular coordinate operations
  - Validation script support for circular distance comparison
affects:
  - 01-foundation-quick-wins
  - 02-a-error-reduction
  - 03-bc-deep-fixes

tech-stack:
  added: []
  patterns:
    - "1-based inclusive coordinates for all genome position math"
    - "Wrap-around position normalization via modulo arithmetic"

key-files:
  created:
    - tests/test_circular_coords.py
  modified:
    - src/mitoflow/models/genome.py
    - scripts/validate_against_gold_standard.py

key-decisions:
  - "circular_distance returns shortest path (min of direct and wrap-around distance)"
  - "circular_span returns forward inclusive span, handling origin crossing"
  - "wrap_position normalizes to [1, length] using 1-based modulo arithmetic"

patterns-established:
  - "All circular coordinate methods live on GenomeSequence model as instance methods"
  - "1-based coordinates are mandatory and validated in tests"

requirements-completed: [BPS-01]

duration: 0min
completed: 2026-04-14
---

# Phase 01: Plan 01 — Circular Genome Coordinate Utilities Summary

**Implemented circular_distance, circular_span, wrap_position, and circular_positions_between on GenomeSequence with 21 passing unit tests and updated gold-standard validation to use circular distance.**

## Performance

- **Duration:** already completed (committed in 861c55d)
- **Started:** 2026-04-14
- **Completed:** 2026-04-14
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added four circular coordinate methods to `GenomeSequence` in `src/mitoflow/models/genome.py`
- Created `tests/test_circular_coords.py` with 21 unit tests covering forward spans, wrap-around spans, origin-adjacent distances, position normalization, and boundary cases
- Updated `scripts/validate_against_gold_standard.py` to compare gene positions using circular distance when genome length is available

## Task Commits

Both tasks were committed together:

1. **Task 1: Add circular_distance and circular_span methods** — `861c55d` (feat)
2. **Task 2: Write circular coordinate unit tests** — `861c55d` (test)

## Files Created/Modified

- `src/mitoflow/models/genome.py` — Added `circular_distance()`, `circular_span()`, `wrap_position()`, `circular_positions_between()`
- `tests/test_circular_coords.py` — 21 pytest cases for circular coordinate logic
- `scripts/validate_against_gold_standard.py` — Added `circular_offset()` and updated `compare_gene_positions()` to use circular distance

## Decisions Made

- `circular_distance(a, b)` returns the shortest path around the circle using `min(abs(a-b), length - abs(a-b))`
- `circular_span(start, end)` uses forward-only inclusive counting, wrapping at the origin
- `wrap_position(pos)` normalizes out-of-range coordinates into `[1, length]` with 1-based modulo math

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Circular coordinate foundation is solid and tested
- Ready for downstream fixes that depend on coordinate wrapping (e.g., multi-exon genes crossing the origin)

---
*Phase: 01-foundation-quick-wins*
*Completed: 2026-04-14*
