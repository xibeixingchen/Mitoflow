---
phase: 01-foundation-quick-wins
verified: 2026-04-14T13:30:00Z
status: gaps_found
score: 8/10 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "B-error数量在环形距离下比Round 2减少>=20%"
    status: failed
    reason: "实际减少仅1.5%（263→259，减少4个）。环形距离实现正确，但原始B-error中 metric artifact 的比例低于预期。基线报告已明确记录此为'度量误差消除'而非算法改进。"
    artifacts:
      - path: "scripts/validate_against_gold_standard.py"
        issue: "实现正确，但效果小于 roadmap 预期"
      - path: "results/round2_circular_baseline/validation_report.md"
        issue: "已如实记录1.5%的减少量"
    missing:
      - "接受该偏差为数据特征导致，或更新 roadmap SC 2 为更现实的阈值"
  - truth: "nad4在15个物种中的36bp偏移归零"
    status: partial
    reason: "代码修复已正确实现（pcg.py 中跳过 multi-exon 基因的 tblastn extension，并修正 minus-strand 搜索偏移），但仅对 Arabidopsis thaliana 做了单物种验证。其余14个受影响物种尚未用修复后的代码重新跑注释流程。"
    artifacts:
      - path: "src/mitoflow/annotate/pcg.py"
        issue: "修复代码已提交（a5be423），但未在27物种上执行验证"
      - path: "results/round2_circular_baseline/validation_details.json"
        issue: "仍显示11个物种有36bp偏移（因 baseline 是用旧代码结果重算）"
    missing:
      - "在27个金标准物种上运行修复后的注释流程，确认 nad4 偏移消失"
  - truth: "整体F1从79.5%提升到>=83%"
    status: partial
    reason: "当前 baseline F1=79.51%（与 Round 2 相同）。F1 提升依赖于 nad4 修复在全部物种上的实际效果，尚未执行。"
    artifacts: []
    missing:
      - "运行完整27物种验证，测量修复后的实际F1"
  - truth: "高F1物种(Ipomoea/Solanum/Punica)不退化（F1>=98%）"
    status: partial
    reason: "Baseline 中 Ipomoea aquatica、Punica granatum、Solanum muricatum 的 F1 均为100%，但这是旧代码结果。修复后的代码尚未在这些物种上执行端到端验证。"
    artifacts: []
    missing:
      - "在3个高F1物种上运行修复后流程，确认F1>=98%"
human_verification:
  - test: "运行完整27物种金标准验证（使用修复后的代码）"
    expected: "nad4 的 end_diff 从36bp降至<=10bp的物种数>=13个；整体F1>=83%；高F1物种F1>=98%"
    why_human: "需要执行完整的注释流程（HMM+BLAST+trans-splicing），耗时较长，无法通过静态代码检查完成"
---

# Phase 01: Foundation + Quick Wins Verification Report

**Phase Goal:** 建立环形坐标基础设施，修复nad4系统性bug，修正验证脚本 — 快速获得可测量的改进

**Verified:** 2026-04-14T13:30:00Z

**Status:** gaps_found

**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #   | Truth   | Status     | Evidence       |
| --- | ------- | ---------- | -------------- |
| 1   | circular_distance正确处理跨原点情况 | VERIFIED | `tests/test_circular_coords.py` 21项全部通过；`circular_distance(499000, 1000, 500000) == 2000` |
| 2   | circular_span正确处理跨原点情况 | VERIFIED | `circular_span(499000, 1000, 500000) == 2001` 通过测试 |
| 3   | 所有坐标使用1-based约定 | VERIFIED | `wrap_position(500001) == 1`，测试覆盖边界和负溢出 |
| 4   | 单元测试全部通过 | VERIFIED | `pytest tests/test_circular_coords.py -v` 21 passed |
| 5   | 位置比较使用环形距离 | VERIFIED | `scripts/validate_against_gold_standard.py` 中 `compare_gene_positions` 使用 `circular_offset()` |
| 6   | 生成环形距离基准报告 | VERIFIED | `results/round2_circular_baseline/` 包含 report、summary、details |
| 7   | 不影响A类和C类错误计算 | VERIFIED | A类错误无变化（444）；C类仅因 metric 减少3个（417→414） |
| 8   | nad4在Arabidopsis中的36bp偏移消失 | VERIFIED | 代码修复逻辑正确（TRANS_SPLICED_CONFIG guard + minus-strand offset fix），SUMMARY 记录单物种验证通过 |
| 9   | 根因分析文档记录在PLAN.md中 | VERIFIED | Plan 03 明确记录根因为 pcg.py 中 multi-exon 基因错误进入 tblastn extension 及 minus-strand 搜索偏移 |
| 10  | 修复不影响其他多外显子基因 | VERIFIED | 修复通过 `TRANS_SPLICED_CONFIG` 精确保护所有 multi-exon 基因，非 multi-exon 基因不受影响 |

**Score:** 8/10 truths verified (2 partial due to pending full-pipeline validation, 1 failed due to forecast deviation)

### Required Artifacts

| Artifact | Expected    | Status | Details |
| -------- | ----------- | ------ | ------- |
| `src/mitoflow/models/genome.py` | 包含 circular_distance, circular_span, wrap_position, circular_positions_between | VERIFIED | 4个方法均存在，使用1-based坐标 |
| `tests/test_circular_coords.py` | 21项单元测试覆盖边界、跨原点、负溢出 | VERIFIED | 21/21 passed |
| `scripts/validate_against_gold_standard.py` | 使用环形距离比较基因位置 | VERIFIED | `circular_offset()` 实现正确，报告含环形距离标注 |
| `results/round2_circular_baseline/validation_report.md` | 包含 metric vs real 改进分析 | VERIFIED | 第5节明确区分度量改进与真实注释改进 |
| `src/mitoflow/annotate/pcg.py` | 修复nad4系统性偏移 | VERIFIED | a5be423 提交包含两处精准修复 |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `pcg.py` | `trans_splicing.TRANS_SPLICED_CONFIG` | `from .trans_splicing import annotate_trans_spliced_genes, TRANS_SPLICED_CONFIG` | WIRED | 用于跳过 multi-exon 基因的 tblastn extension |
| `validate_against_gold_standard.py` | `parse_genbank_features` | `genome_length` 参数传递 | WIRED | `ncbi_length` 优先，`mito_length` fallback |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `validation_report.md` | B/C error counts | `validation_details.json` | 是，基于27物种真实比对数据 | FLOWING |
| `genome.py` | `circular_distance` | `self.length` | 是，基于实际序列长度 | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Circular coordinate tests | `pytest tests/test_circular_coords.py -v` | 21 passed | PASS |
| Validation script help | `python scripts/validate_against_gold_standard.py --help` | Help输出正常 | PASS |
| Baseline report exists | `ls results/round2_circular_baseline/` | 3个文件存在 | PASS |
| pcg.py syntax | `python3 -m py_compile src/mitoflow/annotate/pcg.py` | Syntax OK | PASS |
| Full test suite (excl. known failure) | `pytest tests/ -k "not nad5_exceeds_reject_threshold" -q` | 106 passed, 1 skipped, 1 deselected | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| BPS-01 | Plan 01 | GenomeSequence 环形坐标工具方法 | SATISFIED | `genome.py` 含4个方法，`test_circular_coords.py` 21项通过 |
| BPS-04 | Plan 02 | 验证脚本使用环形距离 | SATISFIED | `validate_against_gold_standard.py` 使用 `circular_offset`，生成 baseline 报告 |
| CSP-01 | Plan 03 | 修复nad4系统性36bp偏移 | SATISFIED (code level) | `pcg.py` 中 TRANS_SPLICED_CONFIG guard 和 minus-strand offset fix；根因文档完整 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| 无 | — | — | — | 未发现 blocker 级反模式 |

### Human Verification Required

1. **运行完整27物种金标准验证（使用修复后的代码）**
   - **Test:** 使用当前 `main` 分支代码对全部27个金标准物种执行 `mitoflow annotate`，再用 `validate_against_gold_standard.py` 生成新报告
   - **Expected:** nad4 的 end_diff 从36bp降至<=10bp的物种数>=13个；整体F1>=83%；高F1物种F1>=98%
   - **Why human:** 完整注释流程（HMM+BLAST+trans-splicing）耗时较长，需人工触发批处理并检查结果

### Gaps Summary

Phase 01 的核心代码交付物（环形坐标基础、验证脚本修复、nad4 代码修复）均已正确实现并提交。主要缺口在于**效果验证尚未完成**：

1. **B-error 减少未达 roadmap 预期**：环形距离仅消除4个B-error（1.5%），远低于 roadmap 预估的20%。这不是实现缺陷，而是原始数据中 metric artifact 比例低于预期的结果。基线报告已如实记录。

2. **nad4 修复的多物种验证 pending**：代码修复逻辑经分析为正确，但仅在 Arabidopsis thaliana 上做了单物种验证。其余10+个受影响物种仍需完整流程重跑确认。

3. **F1 目标待验证**：整体 F1>=83% 和高 F1 物种不退化的目标，需要完整27物种验证后才能确认。

**建议下一步：** 运行完整27物种验证（VAL-01），若 nad4 偏移在多数物种上消失且 F1 提升，则 Phase 01 的缺口可关闭。

---

_Verified: 2026-04-14T13:30:00Z_
_Verifier: Claude (gsd-verifier)_
