---
phase: 03-bc-deep-fixes
gap_closure: false
requirements:
  - BPS-03
  - BPS-05
  - CSP-02
  - CSP-03
  - VAL-03
target_f1: ">=90%"
target_b_error: "<100"
target_c_error: "<150"
---

# Phase 3: B/C Deep Fixes

**Goal:** 深度修复位置偏差（B-error）和剪接位点（C-error）问题，将整体 F1 巩固在 ≥90%。

**Context:**
- Phase 2 A-error 减少已完成，代码已提交。
- 修正后的 Round 2 基线（多 accession 合并修复后）: F1=90.93%, B-error=299, C-error=456
- Phase 2 当前代码结果: F1=91.72%, B-error=283, C-error=414
- B/C 错误仍是 F1 进一步提升的主要瓶颈。

**Top B-error genes (current):**
- cox2: 23 species
- rps10: 17 species
- atp6: 16 species
- rpl16: 15 species
- nad1: 14 species
- rps14: 14 species

**Top C-error genes (current):**
- cox2: 23 species
- cox3: 18 species
- rps4: 18 species
- nad5: 18 species
- nad6: 17 species
- rpl16: 17 species

---

## Wave 1: Boundary Corrections — Remove Hardcoded Offsets + Circular Subsequence

### Plan 01: Make genome.subsequence() support circular coordinates

**Files to modify:**
- `src/mitoflow/models/genome.py`

**Changes:**
1. Modify `subsequence(self, start, end)` to handle `end < start` (origin-crossing).
   - If `end < start`, return `sequence[start-1:] + sequence[:end]`
2. Add unit tests for origin-crossing subsequence in `tests/test_models.py` (or create `tests/test_genome_sequence.py`).

**Verification:**
- Unit test `test_subsequence_crosses_origin`
- Existing tests do not regress

---

### Plan 02: Replace FIXED_OFFSET_GENES with adaptive tblastn boundary refinement in pipeline

**Files to modify:**
- `src/mitoflow/annotate/boundary.py`
- `src/mitoflow/core/pipeline.py`
- `src/mitoflow/annotate/pcg.py` (inspect existing `_refine_boundaries_reference`)

**Changes:**
1. In `boundary.py`, add `_refine_boundary_by_tblastn(ann, genome, db_manager)` helper.
   - Run a local tblastn search using the gene's Protein.fasta reference against the genome.
   - If a high-quality hit (pident ≥ 80%, qcovs ≥ 70%) overlaps the HMM-derived annotation ≥ 80% in length:
     - Use the tblastn hit's `sstart`/`send` as the refined CDS boundary.
   - If the gene is trans-spliced (nad1/nad2/nad5/nad4/etc.), skip or only refine individual exons.
2. In `boundary.py`, update `correct_boundaries()` to call the new helper **before** the fixed offset correction.
3. If the adaptive refinement succeeds and moves the boundary, **skip** the `FIXED_OFFSET_GENES` correction for that gene.
4. Keep `FIXED_OFFSET_GENES` as a fallback for one more validation cycle, but log a warning whenever it is used (so we can measure how many still need it).

**Verification:**
- Run 27-species validation and count how many times FIXED_OFFSET_GENES is still triggered.
- Target: FIXED_OFFSET_GENES usage drops to <5 species.

---

### Plan 03: Integrate circular coordinate support into boundary start/stop search

**Files to modify:**
- `src/mitoflow/annotate/boundary.py`

**Changes:**
1. In `_correct_start_codon_conservative` and `_correct_stop_codon_conservative`, replace `genome.get_sequence_for_range()` calls with a helper that handles origin-crossing.
   - New helper: `_get_sequence_circular(genome, start, end)` which uses the updated `genome.subsequence()`.
2. For reverse strand (`rc_seq`), ensure the reverse complement is computed on the fetched sequence, not on a wrapped range.

**Verification:**
- Unit test with mock genome where a gene's start codon search crosses the origin.
- No regressions on existing boundary tests.

---

## Wave 2: Splice Site and Phase Tracking

### Plan 04: Add splice-site consensus scoring to trans-splicing exon selection

**Files to modify:**
- `src/mitoflow/annotate/trans_splicing.py`

**Changes:**
1. In the exon clustering / hit selection logic, add a helper `_score_splice_sites(genome, exon)`.
   - For each exon, check the 2 bp immediately upstream of `exon.start` (donor) and downstream of `exon.end` (acceptor).
   - Donor consensus: GT (or GC for group II introns). Acceptor consensus: AG.
   - Score adjustment: GT/AG +10, non-consensus -20, GC/AG +5.
   - For genes on the minus strand, check the reverse complement of the genome sequence.
2. When multiple candidate hits overlap an exon region, prefer the one with better splice-site scores.
3. Do **not** hard-reject non-consensus hits; only use it as a tie-breaker/score factor.

**Verification:**
- Unit test `test_splice_site_scoring_prefers_gt_ag`
- 3-species validation: cox2/nad1/nad5 C-error should not increase.

---

### Plan 05: Implement codon phase tracking across exons

**Files to modify:**
- `src/mitoflow/models/gene.py`
- `src/mitoflow/annotate/trans_splicing.py`
- `src/mitoflow/annotate/boundary.py`

**Changes:**
1. Add `phase: int = 0` field to `ExonRecord` (Pydantic model).
2. In `trans_splicing.py`, when merging exons into a multi-exon gene, compute each exon's phase:
   - `phase = (previous_exons_total_length % 3)`
3. After boundary correction in `boundary.py`, if an exon's phase changes (because its length changed), verify phase continuity.
   - If phase is broken (e.g., exon 2 phase should be 1 but boundary shift makes it 2), attempt a ±1bp or ±2bp micro-adjustment of the exon boundary to restore the phase.
   - Only adjust if the shift finds a valid splice-site consensus or keeps the boundary within 3bp of the original.
4. Record phase in `GeneAnnotation.notes` for multi-exon genes.

**Verification:**
- Unit test `test_phase_tracking_across_exons`
- 27-species validation: no regression on trans-spliced gene exact matches.

---

## Wave 3: Validation and Reporting

### Plan 06: Run Round 3 full validation and generate comparison report

**Changes:**
1. Run 27-species batch with Phase 3 code.
2. Run `scripts/validate_against_gold_standard.py`.
3. Compare per-species, per-gene B/C error changes vs Phase 2.
4. Update `.planning/STATE.md` with Phase 3 results.

**Verification:**
- B-error < 100
- C-error < 150
- F1 ≥ 90%
- High-F1 species (Ipomoea/Solanum/Punica) remain ≥ 98%

---

## Success Criteria

1. B-error 从 283 减少到 <100
2. C-error 从 414 减少到 <150
3. FIXED_OFFSET_GENES 硬编码表使用次数 <5 物种（最终移除）
4. 剪接位点共识检查覆盖所有多外显子基因的选择逻辑
5. 整体 F1 保持在 ≥90%
6. 高 F1 物种不退化（F1≥98%）
7. 所有单元测试通过

---

## Execution Order

| Wave | Plan | Scope | Key Deliverable |
|------|------|-------|-----------------|
| 1 | 01 | Circular subsequence in genome.py | `subsequence()` origin-crossing support |
| 1 | 02 | Adaptive tblastn boundary refinement | `_refine_boundary_by_tblastn()` in boundary.py |
| 1 | 03 | Circular coords in boundary start/stop search | `_get_sequence_circular()` helper |
| 2 | 04 | Splice-site consensus scoring | `_score_splice_sites()` in trans_splicing.py |
| 2 | 05 | Phase tracking across exons | `ExonRecord.phase` + continuity validation |
| 3 | 06 | Round 3 validation + report | Full 27-species batch run and comparison |

---

## Risk Flags

- **R1: tblastn-based refinement may over-correct and introduce new B-errors**
  - Mitigation: only accept hits with pident ≥ 80%, overlap ≥ 80%, and keep shift within ±50bp
- **R2: Splice-site consensus may mis-penalize genuine group II introns with non-canonical boundaries**
  - Mitigation: use as scoring tie-breaker, not hard filter; special handling for GC/AG
- **R3: Phase-tracking micro-adjustments may break existing exact matches**
  - Mitigation: only adjust ±1-2bp, and require consensus support
