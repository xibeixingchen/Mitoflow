# MitoFlow 项目更新审查报告

## 更新概览

### 统计对比

| 指标 | 更新前 | 更新后 | 变化 |
|------|--------|--------|------|
| CLI 命令 | 14 个 | 18 个 | +4 |
| 功能模块 | 15 个 | 17 个 | +2 |
| 代码行数 (cli.py) | 526 行 | 739 行 | +213 |
| CMS 基因 | 23 个 | 49 个 | +26 |

---

## 新增功能模块

### 1. NUMT 检测 (`numt/`)
**功能**: 检测核基因组中的线粒体 DNA 片段 (Nuclear Mitochondrial DNA Segment)

**核心能力**:
- BLAST 比对检测 NUMT 区域
- 区分 MTPT (叶绿体来源) 和 NUMT (线粒体来源)
- 基于侧翼核基因和插入上下文分类

**输出**:
```
- NUMT 区域 BED 文件
- 分类报告 (完整/部分/嵌合)
- 覆盖的线粒体基因列表
```

### 2. 重复序列分析 (`repeat/`)
**功能**: 三类重复序列检测

| 子模块 | 功能 | 工具 |
|--------|------|------|
| `ssr.py` | 简单序列重复 (SSR/微卫星) | MISA / Python regex |
| `tandem.py` | 串联重复 | 内置算法 |
| `long_repeat.py` | 长重复序列 | 内置算法 |

**默认阈值** (植物线粒体优化):
- 单核苷酸: 10 次重复
- 双核苷酸: 7 次重复
- 三核苷酸: 6 次重复
- 四-六核苷酸: 5 次重复

---

## 新增 CLI 命令

### 1. `repeat` - 重复序列分析
```bash
mitoflow repeat -i genome.fasta -o output/ [选项]
```
**参数**:
- `--ssr`: 检测微卫星
- `--tandem`: 检测串联重复
- `--long`: 检测长重复
- `--all`: 检测所有类型

### 2. `numt` - NUMT 检测
```bash
mitoflow numt -i nuclear.fasta --mt mito.fasta -o output/
```
**输入**:
- 核基因组 FASTA
- 线粒体基因组 FASTA (参考)

### 3. `gc` - GC 含量分析
```bash
mitoflow gc -i genome.fasta -o output/ [选项]
```
**功能**:
- 滑动窗口 GC 含量
- GC 偏斜 (GC skew) 分析
- 可视化输出

### 4. `phylo-tree` - 系统发育树构建
```bash
mitoflow phylo-tree -i aligned.fasta -o output/ [选项]
```
**功能**:
- 基于多序列比对构建系统发育树
- 支持多种建树方法 (ML, NJ)
- 可视化输出

---

## CMS 数据库更新

### 新增基因 (部分)
| 基因 | 物种 | CMS 类型 | 年份 | 证据 |
|------|------|---------|------|------|
| orf314 | 水稻 | T65-CMS | 2024 | gold |
| orf352 | 水稻 | RT102-CMS | 2023 | gold |
| atp6c | 玉米 | C-CMS | 2022 | gold |
| orf116b | 棉花 | CMS-D2 | 2024 | gold |
| orf346 | 油菜 | Nsa-CMS | 2021 | gold |

**数据库统计**:
- 总基因: 49 个 (来自 17 个物种)
- 高证据: 14 个
- 序列覆盖率: 31/49 (63.3%)

---

## 对 Web 部署的影响

### 新增考虑因素

#### 1. 资源需求变化
| 功能 | 内存需求 | 运行时间 | 优先级 |
|------|---------|---------|--------|
| annotate | 4-8GB | 5min-2h | P0 |
| repeat | 2-4GB | 2-10min | P1 |
| numt | 8-16GB | 10-30min | P1 |
| phylo-tree | 4-8GB | 5-20min | P2 |
| cms | 2-4GB | 5-15min | P1 |

**NUMT 检测** 需要同时加载核基因组和线粒体基因组，内存需求最高。

#### 2. Web 界面设计调整
需要支持的功能模块 (按优先级):
```
Phase 1 (核心):
  ✓ annotate - 完整注释
  ✓ qc - 质量控制
  ✓ viz - 可视化

Phase 2 (重要):
  ✓ repeat - 重复序列
  ✓ cms - CMS 预测
  ✓ mtpt - MTPT 检测

Phase 3 (增强):
  ○ numt - NUMT 检测 (需要双基因组输入)
  ○ phylo-tree - 系统发育
  ○ kaks - 选择压力分析
```

#### 3. 输入复杂性增加
- **NUMT**: 需要两个输入文件 (核基因组 + 线粒体基因组)
- **MTPT**: 需要叶绿体基因组作为参考
- **Phylo**: 需要多序列比对文件

#### 4. 结果展示需求
新增可视化类型:
- SSR 密度图
- 重复序列环形图
- NUMT 分布图 (核基因组坐标)
- GC 含量滑动窗口图
- 系统发育树 (SVG/PNG)

---

## 推荐实施方案

### 功能模块化部署

```
Web 界面分层:
┌─────────────────────────────────────────┐
│  基础分析 (Basic Analysis)               │
│  • 基因组注释 (annotate)                 │
│  • 质量控制 (qc)                         │
│  • 可视化 (viz)                          │
├─────────────────────────────────────────┤
│  特征分析 (Feature Analysis)             │
│  • 重复序列 (repeat)                     │
│  • CMS 预测 (cms)                        │
│  • MTPT 检测 (mtpt)                      │
│  • GC 分析 (gc)                          │
├─────────────────────────────────────────┤
│  高级分析 (Advanced Analysis)            │
│  • NUMT 检测 (numt) - 需要核基因组       │
│  • 比较基因组 (kaks, synteny)            │
│  • 系统发育 (phylo, phylo-tree)          │
└─────────────────────────────────────────┘
```

### 资源隔离策略

```yaml
Worker 分级:
  standard:
    memory: 4GB
    cpu: 2
    tasks: [annotate, qc, viz, gc]
    
  medium:
    memory: 8GB
    cpu: 4
    tasks: [repeat, cms, mtpt, phylo]
    
  large:
    memory: 16GB
    cpu: 8
    tasks: [numt, kaks, synteny]
```

### API 扩展

```yaml
新增端点:
  POST /api/repeat:
    summary: 重复序列分析
    
  POST /api/numt:
    summary: NUMT 检测
    parameters:
      - nuclear_file: 核基因组
      - mito_file: 线粒体基因组
      
  POST /api/gc:
    summary: GC 含量分析
    
  POST /api/phylo-tree:
    summary: 系统发育树构建
```

---

## 开发建议

### 短期 (1-2周)
1. 优先实现核心功能 Web 化 (annotate + qc + viz)
2. 重复序列分析 (repeat) 用户友好度高，优先实现
3. CMS 预测功能相对独立，易于实现

### 中期 (3-4周)
4. NUMT 检测 (需要处理双文件上传，界面设计复杂)
5. GC 分析 (相对简单，快速上线)

### 长期 (按需)
6. 比较基因组学功能 (kaks, synteny, phylo)
7. 高级可视化集成

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| NUMT 内存溢出 | 高 | 高 | 16GB 专用 Worker，超时控制 |
| 多文件上传复杂 | 中 | 中 | 分步向导式界面 |
| 长时间任务堆积 | 中 | 高 | 队列优先级，自动扩容 |
| 大文件传输失败 | 中 | 中 | 断点续传，分片上传 |

