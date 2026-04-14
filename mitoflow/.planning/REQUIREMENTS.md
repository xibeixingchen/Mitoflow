# Requirements: MitoFlow Round 3

**Defined:** 2026-04-14
**Core Value:** 准确的基因注释 — 每个基因在正确的位置、正确的边界

## v1 Requirements

### A类：假阳性基因过滤

- [ ] **AFP-01**: 实现分基因家族HMM阈值 — rps/rpl ≥60, 核心PCG(nad/cox/atp/cob) ≥40, 其他 ≥50
- [ ] **AFP-02**: 为高频误检基因(rps19/mttb/sdh4)添加存在性验证规则
- [ ] **AFP-03**: 集成基因长度校验，超出预期范围(50%-150%)的基因标记为低置信度
- [ ] **AFP-04**: 改进重复基因过滤逻辑，区分真重复与假阳性

### B类：位置偏差修正

- [ ] **BPS-01**: 在GenomeSequence模型中实现circular_distance()和circular_span()工具方法
- [ ] **BPS-02**: 将环形坐标计算集成到外显子合并逻辑(trans_splicing.py)
- [ ] **BPS-03**: 将环形坐标计算集成到边界校正逻辑(boundary.py)
- [ ] **BPS-04**: 验证脚本使用环形距离比较基因位置，替代线性距离
- [ ] **BPS-05**: 用自适应tblastn比对边界替代硬编码的FIXED_OFFSET_GENES表

### C类：剪接位点改进

- [ ] **CSP-01**: 排查并修复nad4在15个物种中一致的36bp偏移bug
- [ ] **CSP-02**: 添加剪接位点共识验证(GT/AG, 允许GC/AG)在外显子选择时
- [ ] **CSP-03**: 实现外显子间可读框相位(phase)追踪，确保密码子连续性

### 验证与回归

- [ ] **VAL-01**: 每次改动后在27个金标准物种上运行完整验证
- [ ] **VAL-02**: 跟踪高F1物种(Ipomoea/Solanum/Punica)确保不退化
- [ ] **VAL-03**: 生成Round 3验证报告，包含新旧指标对比

## v2 Requirements（延迟到Round 4）

### 数据库扩展

- **DB-01**: 扩充HMM profile数据库，增加更多参考物种
- **DB-02**: 更新blast_refs参考序列到最新版本
- **DB-03**: 清理pcg/pcg_new/pcg_v2/backup_old重复目录

### RNA编辑

- **RNA-01**: RNA编辑位点感知的起始密码子检测
- **RNA-02**: C-to-U编辑校正整合到边界校正流程

## Out of Scope

| 特性 | 排除原因 |
|------|---------|
| Web界面改进 | 独立里程碑，与注释精度无关 |
| 新分析模块 | Round 3聚焦注释精度，不增加新功能 |
| 数据库大扩展 | 需要系统性整理，Round 4任务 |
| 物种特异性规则 | 应该基于基因家族规则，不是物种hack |
| 降低HMM阈值 | min_score=30已经很低，降低会增加假阳性 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AFP-01 | Phase 2 | Pending |
| AFP-02 | Phase 2 | Pending |
| AFP-03 | Phase 2 | Pending |
| AFP-04 | Phase 2 | Pending |
| BPS-01 | Phase 1 | Pending |
| BPS-02 | Phase 2 | Pending |
| BPS-03 | Phase 3 | Pending |
| BPS-04 | Phase 1 | Pending |
| BPS-05 | Phase 3 | Pending |
| CSP-01 | Phase 1 | Pending |
| CSP-02 | Phase 3 | Pending |
| CSP-03 | Phase 3 | Pending |
| VAL-01 | All | Pending |
| VAL-02 | All | Pending |
| VAL-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after initial definition*
