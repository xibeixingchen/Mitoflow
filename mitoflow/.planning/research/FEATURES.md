# Features Research — MitoFlow Round 3

**Researched:** 2026-04-14

## Table Stakes (Must Have for Accurate Annotation)

### FS-01: Per-Gene HMM Score Thresholds
- Different gene families need different stringency
- Ribosomal proteins (rps/rpl) need higher thresholds (≥60) — they're the top false-positive source
- Core PCG (nad/cox/atp/cob) can stay at lower thresholds (≥40)
- **Complexity: Low** — modify PCGConfig and filtering logic

### FS-02: Circular Genome Coordinate Math
- Distance/span calculations must handle wrap-around for circular genomes
- Affects: exon merging, boundary correction, validation comparison
- Critical for large genomes (>500kb) where multi-exon genes span origin
- **Complexity: Medium** — utility functions + apply throughout

### FS-03: nad4 Splice Site Fix
- Systematic 36bp offset across 15 species — clearly a bug
- Must identify root cause (likely codon phase or exon boundary error)
- Fix should resolve C errors for all 15 affected species at once
- **Complexity: Low-Medium** — targeted fix once root cause found

### FS-04: False Positive Gene Filtering
- rps19 detected in 12 species where it shouldn't be
- mttb detected in 11 species as false positive
- Need gene-specific presence/absence rules based on plant mitochondrial biology
- **Complexity: Medium** — requires biological knowledge + per-gene rules

### FS-05: Gene Length Validation
- Compare detected gene length against expected range
- Flag genes that are too short (<50%) or too long (>150%) as suspicious
- Use expected ranges from cds_check.py GENE_LENGTH_RANGES
- **Complexity: Low** — leverage existing data

### FS-06: Validation Script Circular Distance Fix
- Position comparison must use circular distance
- Currently uses linear distance — incorrect for circular genomes
- Fixes many B errors without touching annotation code
- **Complexity: Low** — single function change

## Differentiators (Would Improve Quality Further)

### FD-01: Splice Site Consensus Validation
- Validate GT/AG (or GC/AG) motifs at exon-intron boundaries
- Score exons by splice site quality, not just BLAST alignment score
- Would improve C errors across all multi-exon genes
- **Complexity: Medium-High**

### FD-02: Reading Frame Phase Tracking
- Track codon phase (0, 1, 2) across exons
- Ensure frame continuity when merging exons
- Detect and correct frame shifts
- **Complexity: Medium**

### FD-03: Weighted Validation Scoring
- Exclude poorly-annotated species from A-error calculations
- Weight B errors by magnitude (50bp offset ≠ 100000bp offset)
- Separate precision/recall for core vs accessory genes
- **Complexity: Low**

### FD-04: Per-Species Boundary Correction
- Replace FIXED_OFFSET_GENES with adaptive boundary correction
- Use tblastn alignment start/end positions instead of hardcoded offsets
- Species-specific correction based on best tblastn hit
- **Complexity: Medium**

## Anti-Features (Do NOT Implement)

### FX-01: Do NOT lower HMM thresholds further
- min_score=30 is already very permissive
- Lowering would increase false positives

### FX-02: Do NOT remove trans-spliced gene detection
- Even with errors, detecting multi-exon genes is better than missing them
- Fix the detection, don't disable it

### FX-03: Do NOT hardcode species-specific rules
- Rules should be gene-family based, not species-based
- Species-specific hacks create maintenance burden

### FX-04: Do NOT change gold standard species
- Better to improve annotation than cherry-pick easy species
- Can add weighted scoring but don't remove species

## Dependencies Between Features

```
FS-02 (circular coords) → FD-01 (splice site validation)
FS-02 (circular coords) → FS-06 (validation fix)
FS-03 (nad4 fix) → independent (specific bug)
FS-01 (per-gene thresholds) → FS-04 (false positive filtering)
FS-05 (length validation) → FS-04 (false positive filtering)
FD-04 (adaptive boundary) → replaces FIXED_OFFSET_GENES
```

## Priority Order

1. FS-02 (circular coords) — foundational, unblocks many fixes
2. FS-06 (validation circular fix) — quick win, fixes B errors in validation
3. FS-03 (nad4 fix) — high-impact, 15 species at once
4. FS-01 (per-gene thresholds) — reduces A errors at source
5. FS-04 + FS-05 (false positive filtering) — further reduce A errors
6. FD-01 (splice site consensus) — improves C errors
7. FD-04 (adaptive boundary) — replaces hardcoded offsets
