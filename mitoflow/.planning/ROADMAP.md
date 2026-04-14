# Roadmap: MitoFlow Round 3

**Created:** 2026-04-14
**Granularity:** Coarse (3 phases)
**Total Requirements:** 15

---

## Phase 1: Foundation + Quick Wins

**Goal:** 建立环形坐标基础设施，修复nad4系统性bug，修正验证脚本 — 快速获得可测量的改进

**Requirements:** BPS-01, BPS-04, CSP-01, VAL-01, VAL-02

### Tasks

1. **在GenomeSequence中实现环形坐标工具方法**
   - `circular_distance(a, b)` — 计算环形基因组上两点的最短距离
   - `circular_span(start, end)` — 计算正向跨度
   - 单元测试覆盖边界情况（跨越原点、刚好在原点上等）

2. **修复验证脚本的环形距离比较**
   - `validate_against_gold_standard.py` 中位置比较改用环形距离
   - 生成Round 2基准（用环形距离重算），得到真实B-error基线
   - 这一步可能大幅减少B-error计数（很多大偏差是度量误差而非注释误差）

3. **排查并修复nad4系统性36bp偏移**
   - 分析nad4外显子边界计算逻辑
   - 检查是否是密码子相位(phase)计算错误（36bp = 12 codons）
   - 在trans_splicing.py中定位具体代码
   - 修复后在15个受影响物种上验证

4. **建立回归测试流程**
   - 每次改动后运行27物种验证
   - 跟踪高F1物种(Ipomoea/Solanum/Punica)确保≥98%
   - 记录每次改动的指标变化

### Success Criteria

1. circular_distance/circular_span通过所有单元测试
2. B-error数量在环形距离下比Round 2减少≥20%
3. nad4在15个物种中的36bp偏移归零
4. 高F1物种(Ipomoea/Solanum/Punica)不退化（F1≥98%）
5. 整体F1从79.5%提升到≥83%

---

## Phase 2: A-Error Reduction

**Goal:** 减少假阳性基因检出（A错误从444降至<200），同时保持敏感性≥92%

**Requirements:** AFP-01, AFP-02, AFP-03, AFP-04, BPS-02

### Tasks

1. **实现分基因家族HMM阈值**
   - 在pcg.py中添加PER_GENE_MIN_SCORES字典
   - rps/rpl家族: min_score=60
   - 核心PCG(nad/cox/atp/cob): min_score=40
   - 其他(ccm/mat/sdh/mtt): min_score=50
   - 替换当前的统一min_score=30

2. **添加高频误检基因的过滤规则**
   - rps19: 在大多数植物线粒体中已丢失，需要高置信度才保留
   - mttb: 不是所有植物都有，添加存在性检查
   - sdh4: 经常是假阳性，添加额外长度/分数验证

3. **集成基因长度校验**
   - 使用cds_check.py中已有的GENE_LENGTH_RANGES
   - 检出基因长度超出50%-150%范围时标记为低置信度
   - 低置信度基因在最终输出中标注，但不删除

4. **改进重复基因过滤**
   - 区分真重复（同一基因多个功能拷贝）和假阳性
   - 核心PCG保留单拷贝最佳匹配
   - 非核心基因允许双拷贝

5. **环形坐标集成到trans_splicing.py**
   - exon合并时使用circular_span计算外显子间距
   - 修复大基因组中跨原点的多外显子基因

### Success Criteria

1. A-error从444减少到<200
2. Sensitivity保持在≥92%（不能过度过滤）
3. rps19假阳性从12物种减少到<3物种
4. 整体F1从Phase 1结果提升到≥87%
5. 低F1物种(Glycine max, Capsicum annuum)改善≥10个百分点

---

## Phase 3: B/C Deep Fixes

**Goal:** 深度修复位置偏差和剪接位点问题，F1达到≥90%目标

**Requirements:** BPS-03, BPS-05, CSP-02, CSP-03, VAL-03

### Tasks

1. **环形坐标集成到boundary.py**
   - 起始/终止密码子搜索使用环形距离
   - 跨越原点的基因正确处理边界

2. **自适应边界校正替代FIXED_OFFSET_GENES**
   - 删除硬编码的FIXED_OFFSET_GENES表
   - 改用tblastn比对结果的alignment边界作为校正基准
   - 当tblastn hit覆盖HMM hit区域≥80%时，采用tblastn边界
   - 对cox2/rps10/nad7/rps14等重点验证

3. **添加剪接位点共识验证**
   - 在trans_splicing.py的外显子选择步骤中
   - 检查外显子-内含子边界的GT/AG共识（允许GC/AG）
   - 作为评分因子（不是硬过滤），GT/AG +10分，非共识 -20分
   - 不应用于group II intron的短外显子

4. **实现可读框相位追踪**
   - 追踪每个外显子的密码子相位(0, 1, 2)
   - 合并外显子时验证相位连续性
   - 相位不连续时尝试±1bp微调外显子边界
   - 记录相位信息到GeneAnnotation

5. **生成Round 3验证报告**
   - 完整27物种验证结果
   - 与Round 1/Round 2指标对比
   - 分物种、分基因、分错误类型的详细分析
   - 标注哪些改进来自度量变化vs真实注释改进

### Success Criteria

1. B-error从Round 2的263减少到<100
2. C-error从Round 2的417减少到<150
3. FIXED_OFFSET_GENES完全移除，由自适应方法替代
4. 剪接位点共识检查覆盖所有多外显子基因
5. 整体F1达到≥90%（最终目标）
6. 高F1物种保持≥98%

---

## Phase Summary

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|-------------|-----------------|
| 1 | Foundation + Quick Wins | 环形坐标+nad4修复+验证修复 | BPS-01, BPS-04, CSP-01, VAL-01, VAL-02 | 5 |
| 2 | A-Error Reduction | 假阳性过滤 | AFP-01, AFP-02, AFP-03, AFP-04, BPS-02 | 5 |
| 3 | B/C Deep Fixes | 位置偏差+剪接位点 | BPS-03, BPS-05, CSP-02, CSP-03, VAL-03 | 6 |

**Coverage:** 15/15 requirements mapped ✓
