---
phase: 02-a-error-reduction
gap_closure: false
requirements:
  - AFP-01
  - AFP-02
  - AFP-03
  - AFP-04
  - BPS-02
target_f1: ">=87%"
target_a_error: "<200"
---

# Phase 2: A-Error Reduction

**Goal:** 将假阳性基因检出（A-error）从 444 降至 <200，同时保持敏感性 ≥92%，整体 F1 提升至 ≥87%。

**Context:**
- Phase 1 已完成环形坐标基础设施和 nad4 修复。
- 当前基线（Round 2 circular baseline）: Accuracy=71.86%, Sensitivity=92.94%, F1=79.51%
- A-error=444 是提升 F1 的最大瓶颈，主要来源：
  - 统一的 HMM min_score=30 过于宽松，导致 rps/rpl 等可变基因家族大量假阳性
  - 已丢失基因（如 rps19）被错误召回
  - 重复基因过滤策略过于简单（仅保留最长），未能区分真重复与假阳性
  - 基因长度缺乏系统校验，超长/超短 hit 未标记

---

## Wave 1: Thresholds, Filters, and Length Validation

### Plan 01: Per-gene-family HMM thresholds and high-FPR gene filters

**Files to modify:**
- `src/mitoflow/annotate/pcg.py`

**Changes:**
1. Add `PER_GENE_MIN_SCORES` dictionary after `PCGConfig`.
   - rps/rpl family: min_score=60
   - Core PCG (nad/cox/atp/cob): min_score=40
   - Others (ccm/mat/sdh/mtt): min_score=50
   - Default fallback: min_score=30
2. Replace `config.min_score` checks with `_get_min_score(gene_name, config)` helper.
3. Add presence-based filters:
   - `rps19`: require score >= 80 AND length within 50-150aa to retain
   - `mttb`: require score >= 60 (not universally present)
   - `sdh4`: require score >= 60 AND no internal stop codon

**Verification:**
- Unit test `test_per_gene_min_scores_applies_correctly`
- Run 3-species quick validation (Arabidopsis, Raphanus, Glycine) and confirm A-error reduction

### Plan 02: Integrate gene length validation

**Files to modify:**
- `src/mitoflow/annotate/pcg.py`
- `src/mitoflow/annotate/cds_check.py` (if extension needed)

**Changes:**
1. Import `GENE_LENGTH_RANGES` from `cds_check.py` into `pcg.py`.
2. After HMM hit passes score threshold, compute `length_ratio = hit_length_aa / expected_length`.
3. If ratio < 0.5 or ratio > 1.5:
   - Do NOT delete the gene automatically
   - Mark `confidence = "Low"` and add a warning tag to `GeneAnnotation.notes` (or metadata dict)
4. For ratio < 0.3 or > 2.0, apply stricter filtering (require score +20 above min threshold).

**Verification:**
- Unit test `test_length_validation_flags_outliers`
- Confirm no regression on core PCG exact matches in 3-species test

---

## Wave 2: Duplicate Filtering and Circular Coordinates in Trans-Splicing

### Plan 03: Improve duplicate gene filtering logic

**Files to modify:**
- `src/mitoflow/annotate/pcg.py`

**Changes:**
1. Refactor duplicate filtering in `annotate_pcg()` around line 396-428.
2. Distinguish core PCG vs variable genes:
   - Core PCG (`CORE_PCG_41`): keep single best copy (highest score, not just longest)
   - Variable genes (rps/rpl/sdh/mtt): allow up to 2 copies if both pass min_score
3. If a second copy has score < 0.7 * best_copy_score, filter it out regardless of length.
4. Add `config.max_pcg_copies` (default 2 for non-core, 1 for core).

**Verification:**
- Unit test `test_duplicate_filtering_keeps_best_core_copy`
- 3-species validation: no core PCG duplicated, no false loss of real duplicates

### Plan 04: Circular coordinate integration in trans_splicing.py

**Files to modify:**
- `src/mitoflow/annotate/trans_splicing.py`
- `src/mitoflow/models/genome.py` (ensure methods available)

**Changes:**
1. Import `circular_span` from `genome.py` (or pass `genome_length` to exon distance functions).
2. In exon clustering / merging logic, replace linear distance `abs(exon2.start - exon1.end)` with `circular_span(exon1.end, exon2.start, genome_length)`.
3. Fix cases where trans-spliced exons are on opposite sides of the origin in large genomes.
4. Add regression test: `test_trans_spliced_exons_across_origin`.

**Verification:**
- New unit test passes with origin-crossing mock data
- 3-species validation: no new C-error or B-error regressions

---

## Success Criteria

1. A-error 从 444 减少到 <200
2. Sensitivity 保持在 ≥92%
3. rps19 假阳性从基线水平减少到 <3 物种
4. 整体 F1 从 Phase 1 基线提升到 ≥87%
5. 低 F1 物种 (Glycine max, Capsicum annuum) 改善 ≥10 个百分点
6. 单元测试全部通过 (`pytest tests/test_annotate*.py -v`)
7. 高 F1 物种 (Ipomoea/Solanum/Punica) 不退化（F1≥98%）

---

## Execution Order

| Wave | Plan | Scope | Key Deliverable |
|------|------|-------|-----------------|
| 1 | 01 | Per-gene HMM thresholds + gene filters | `PER_GENE_MIN_SCORES`, rps19/mttb/sdh4 filters |
| 1 | 02 | Length validation integration | Length ratio checks, low-confidence flags |
| 2 | 03 | Duplicate filtering improvements | Score-aware duplicate rules for core/variable genes |
| 2 | 04 | Circular coords in trans_splicing | `circular_span` in exon merging, regression test |

---

## Risk Flags

- **R1: Over-filtering causing sensitivity drop below 92%**
  - Mitigation: thresholds are conservative (only raised for rps/rpl and known false positives); length outliers are flagged, not deleted
- **R2: Duplicate filtering removing real mitochondrial duplicates**
  - Mitigation: variable genes explicitly allowed 2 copies; core genes are almost universally single-copy in plant mitochondria
- **R3: trans_splicing circular coordinate change introducing new exon-merging bugs**
  - Mitigation: comprehensive unit test with origin-crossing cases; 3-species regression check
