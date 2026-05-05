# AI 工具扩展计划：线粒体 + 叶绿体双细胞器覆盖

## 现状盘点

### 当前已注册工具（~22 个）

| 类别 | 工具名 | 功能 | 细胞器 |
|------|--------|------|--------|
| 核心 | `run_annotation` | FASTA → 注释 (PCG/tRNA/rRNA) | 线粒体 |
| 核心 | `run_visualization` | circular/linear/ogdraw/gc 图 | 线粒体 |
| 核心 | `list_workspace_files` | 列出会话工作区文件 | 通用 |
| 核心 | `summarize_result_directory` | 汇总结果目录 | 通用 |
| 核心 | `list_mitoflow_modules` | 列出模块 | 通用 |
| Skills | `execute_skill` | 执行 skill | 混合 |
| Skills | `list/get/find_skills` | Skill 查询 | 通用 |
| 叶绿体 | `cgas_assemble` ~ `cgas_phylogeny` | 14 个叶绿体专用模块 | 叶绿体 |
| 叶绿体 | `cgas_list_modules` / `cgas_run_pipeline` | CGAS 聚合工具 | 叶绿体 |
| Web | `web_search_literature` | 文献检索 | 通用 |
| Web | `web_lookup_github` | GitHub 工具查询 | 通用 |
| Web | `web_fetch_page` | 网页抓取 | 通用 |
| 知识 | `search_genes` / `gene_info_lookup` | 基因数据库查询 | 线粒体为主 |
| MCP | `search_references` / `get_reference` | 参考文献 MCP | 线粒体为主 |
| Wiki | `search_wiki` / `get_wiki_page` | Wiki 知识查询 | 线粒体为主 |
| Deep | `deep_research` / `deep_analysis` | DeepAgent 工具 | 通用 |

### 线粒体模块清单（MITOFLOW_MODULES）

```
annotate, qc, viz, mtpt, rna-edit, codon, multiconf, kaks, synteny, pi, phylo, cms, validate-rna, report, repeat, numt, gc, phylo-tree
```

**问题**：这 18 个模块中，只有 `annotate` 和 `viz` 被注册为 AI 工具。其余 16 个模块用户只能通过 CLI 使用，AI 无法调用。

---

## 命名规范（已统一）

**线粒体工具**：以 `线粒体` / `mito_` 语义前缀（内部注册名使用英文，用户可见描述用中文）
**叶绿体工具**：以 `叶绿体` / `chloro_` 语义前缀

| 旧名称 | 新名称 | 说明 |
|--------|--------|------|
| `cgas_assemble` | `叶绿体组装` / `chloro_assemble` | 叶绿体基因组组装 |
| `cgas_annotate` | `叶绿体注释` / `chloro_annotate` | 叶绿体基因组注释 |
| `cgas_codon` | `叶绿体密码子分析` / `chloro_codon` | 密码子使用分析 |
| `cgas_phylogeny` | `叶绿体系统发育` / `chloro_phylogeny` | 系统发育矩阵构建 |
| `run_annotation` | `线粒体注释` / `mito_annotate` | 线粒体基因组注释 |
| `run_visualization` | `线粒体可视化` / `mito_visualize` | 线粒体基因组可视化 |
| `run_qc` | `线粒体质控` / `mito_qc` | 基因组质量评估 |

---

## 叶绿体工具缺口分析

### 已覆盖（CGAS 14 模块 → 已去前缀）
- assembly, annotate, compare, convert, gene_compare, gene_table, genome_compare, codon, amino, snp, intron, ssr, diversity, phylogeny

### 未覆盖的叶绿体特异性分析

| # | 功能 | 叶绿体重要性 | 复用度 |
|---|------|-------------|--------|
| 1 | **IR 边界分析** (LSC/IRb/SSC/IRa) | 高 — 四分区结构是叶绿体基因组标志性特征 | 低（线粒体无 IR） |
| 2 | **光合作用基因集分析** (psa/psb/pet/rbcL/ndh) | 高 — 叶绿体核心功能 | 低（线粒体无） |
| 3 | **叶绿体 RNA 编辑** (C-to-U, ~30-50 sites) | 中 — 少于线粒体但仍有研究价值 | 中（与线粒体 rna-edit 模块架构类似） |
| 4 | **ndh 基因家族完整性检测** | 中 — 11 个 ndh 基因在部分物种中丢失 | 低 |
| 5 | **叶绿体-线粒体 MTPT 互作** | 高 — 双向 DNA 转移 | 高（线粒体已有 mtpt 模块，可扩展为双向） |
| 6 | **IR 扩张/收缩可视化** | 中 — 进化研究常用 | 低 |
| 7 | **叶绿体基因组 GC skew 分析** | 中 — Origin of replication 研究 | 高（与线粒体 gc 模块复用） |

---

## 线粒体-叶绿体复用矩阵

```
                    线粒体        叶绿体       复用策略
annotate            ✅ 已注册     ✅ CGAS       各自独立（遗传密码不同）
assembly            ❌ 未注册     ✅ CGAS       新增：基于文献的组装工具集
qc                  ❌ 未注册     ✅ CGAS       复用：统一 QC 接口
codon               ❌ 未注册     ✅ CGAS       复用：统一密码子分析工具
gc                  ❌ 未注册     ✅ CGAS       复用：统一 GC 分析工具
phylo/phylo-tree    ❌ 未注册     ✅ CGAS       复用：统一系统发育工具
kaks                ❌ 未注册     ❌ 缺失       新增：双细胞器 Ka/Ks
synteny             ❌ 未注册     ❌ 缺失       新增：双细胞器共线性
repeat              ❌ 未注册     ❌ 缺失       新增：双细胞器重复序列
numt                ❌ 未注册     ❌ 缺失       新增：线粒体 NUMT + 叶绿体 NUPT
mtpt                ❌ 未注册     ❌ 缺失       扩展：MTPT + PTMT 双向检测
rna-edit            ❌ 未注册     ❌ 缺失       复用：统一 RNA 编辑分析
cms                 ❌ 未注册     N/A          保持线粒体专用
multiconf           ❌ 未注册     ❌ 缺失       新增：双细胞器多构型
report              ❌ 未注册     ❌ 缺失       新增：双细胞器综合报告
validate-rna        ❌ 未注册     ❌ 缺失       新增：RNA-seq 验证（已在做）
```

**关键洞察**：线粒体有 18 个模块但 AI 只能调用 2 个；叶绿体有 14 个 CGAS 模块但工具名不统一。
**最大收益**：把线粒体的 16 个未注册模块注册为 AI 工具，同时扩展 7 个叶绿体专用工具，即可实现双细胞器全面覆盖。

---

## 组装工具集（新增，基于文献）

### 文献依据

**核心综述**：Ni et al. (2025) "Advance in the assembly of the plant mitochondrial genomes using high-throughput DNA sequencing data of total cellular DNAs" *Plant Biotechnology Journal*. DOI: 10.1111/pbi.70249

**该综述评估了 13 个工具，主要发现**：
- **连续性/完整性最佳**：SMARTdenovo, NextDenovo, Oatk
- **正确性最佳**：GetOrganelle, Flye
- **长读长组装器**：Canu, Flye, SMARTdenovo, NextDenovo, TIPPo
- **专用细胞器工具**：Oatk (专门针对植物细胞器), GetOrganelle (混合组装), POLAP (质体-线粒体联合组装)
- **混合策略**：ONT 长读 + Illumina 短读校正

### 线粒体组装工具

| 工具名 | 功能 | 后端实现 | 安全级别 |
|--------|------|----------|----------|
| `线粒体组装` / `mito_assemble` | 植物线粒体基因组组装（长读/混合） | 封装 Oatk/GetOrganelle/Flye | LAUNCHES_JOB |
| `线粒体组装评估` / `mito_assembly_eval` | 组装质量评估（完整性/正确性） | QUAST + 自定义指标 | READ_ONLY |
| `线粒体基因组圈化` / `mito_circularize` | 检查并完成环状基因组 | 基于重复序列的圈化 | WRITES_OUTPUT |

### 叶绿体组装工具

| 工具名 | 功能 | 后端实现 | 安全级别 |
|--------|------|----------|----------|
| `叶绿体组装` / `chloro_assemble` | 叶绿体基因组组装 | 封装 GetOrganelle/Oatk | LAUNCHES_JOB |
| `叶绿体组装评估` / `chloro_assembly_eval` | 组装质量评估 | QUAST + IR 完整性检查 | READ_ONLY |

### 组装策略参数

```python
# 组装策略选择（基于 Ni et al. 2025 文献建议）
ASSEMBLY_STRATEGIES = {
    "hifi_only": {
        "tools": ["oatk", "flye", "nextdenovo"],
        "description": "PacBio HiFi 长读长单独组装，推荐 Oatk 首选",
        "literature_ref": "Ni2025_Fig3"
    },
    "ont_only": {
        "tools": ["flye", "nextdenovo", "smartdenovo"],
        "description": "ONT 长读长单独组装，连续性优先选 NextDenovo",
        "literature_ref": "Ni2025_Fig3"
    },
    "hybrid": {
        "tools": ["getorganelle", "polap"],
        "description": "ONT/HiFi + Illumina 混合组装，正确性优先",
        "literature_ref": "Ni2025_Fig4"
    },
    "short_read": {
        "tools": ["getorganelle", "novoplasty"],
        "description": "仅 Illumina 短读长，适用于低深度样本",
        "literature_ref": "Ni2025_Table1"
    }
}
```

---

## 新增工具列表（按优先级）

### P0 — 高优先级（立即实施）

| 工具名 | 功能 | 来源 | 安全级别 |
|--------|------|------|----------|
| `线粒体组装` / `mito_assemble` | 基因组组装（长读/混合） | 新：基于 Ni et al. 2025 | LAUNCHES_JOB |
| `叶绿体组装` / `chloro_assemble` | 叶绿体基因组组装 | 复用 CGAS module 1 | LAUNCHES_JOB |
| `线粒体质控` / `mito_qc` | 基因组质量评估 | 复用 `skills_tools._run_qc_skill` | WRITES_OUTPUT |
| `线粒体密码子分析` / `mito_codon` | 密码子使用分析 (RSCU) | 复用 CGAS module 8 + 线粒体 codon | READ_ONLY |
| `线粒体GC分析` / `mito_gc` | GC 含量 / GC skew 分析 | 复用 `viz.gc_content` | WRITES_OUTPUT |
| `线粒体系统发育` / `mito_phylogeny` | 系统发育矩阵构建 | 复用 `pi` + `phylo` 模块 | LAUNCHES_JOB |
| `线粒体KaKs分析` / `mito_kaks` | Ka/Ks 选择压力分析 | 复用 `kaks` 模块 | LAUNCHES_JOB |
| `线粒体重复序列` / `mito_repeat` | 重复序列检测 | 复用 `repeat` 模块 | READ_ONLY |
| `线粒体NUMT检测` / `mito_numt` | NUMT / NUPT 检测 | 复用 `numt` 模块，扩展 NUPT | READ_ONLY |
| `线粒体MTPT分析` / `mito_mtpt` | MTPT / PTMT 双向检测 | 复用 `mtpt` 模块，扩展 PTMT | READ_ONLY |

### P1 — 中优先级（下周实施）

| 工具名 | 功能 | 来源 |
|--------|------|------|
| `线粒体RNA编辑` / `mito_rna_edit` | RNA 编辑位点预测与统计 | 复用 `rna-edit` 模块，扩展叶绿体 |
| `线粒体共线性` / `mito_synteny` | 共线性分析 | 复用 `synteny` 模块 |
| `线粒体多构型` / `mito_multiconf` | 多构型基因组分析 | 复用 `multiconf` 模块 |
| `线粒体CMS检测` / `mito_cms` | CMS 基因预测 | 复用 `skills_tools._run_cms_skill` |
| `生成报告` / `generate_report` | 综合 HTML/PDF 报告生成 | 复用 `report` 模块 |
| `RNAseq验证` / `validate_with_rna_seq` | RNA-seq 验证边界/剪接 | 复用 `validate-rna` 模块 |

### P2 — 叶绿体专用（后续迭代）

| 工具名 | 功能 | 说明 |
|--------|------|------|
| `叶绿体IR边界分析` / `chloro_ir_boundary` | IR 区边界分析 (JLB/JSB/JSA/JLA) | 叶绿体标志性分析 |
| `叶绿体光合作用基因` / `chloro_photosynthesis` | 光合作用基因完整性检测 | psa/psb/pet/rbcL/ndh |
| `叶绿体ndh完整性` / `chloro_ndh` | ndh 基因家族完整性 | 11 个 ndh 基因 |
| `叶绿体RNA编辑` / `chloro_rna_edit` | 叶绿体 C-to-U 编辑位点 | ~30-50 sites，少于线粒体 |
| `叶绿体IR可视化` / `chloro_ir_viz` | IR 扩张/收缩可视化 | 进化研究 |

---

## 复用策略详解

### 1. 线粒体模块 → AI 工具（最简单，收益最高）

现有 `MITOFLOW_MODULES` 中的 16 个未注册模块都有对应的 CLI 命令和 Python API。注册为 AI 工具只需：
- 在 `mitoflow_tools.py` 中添加 `ToolDefinition`
- 包装现有函数为 `(args, context) -> Dict` 签名
- 统一参数解析（workspace 路径解析、输出目录管理）

**示例**：`线粒体质控` 可以直接复用 `_run_qc_skill` 的实现。

### 2. CGAS 叶绿体模块 → 统一接口（去前缀）

14 个叶绿体工具已注册但带有 `cgas_` 前缀。需要：
- 移除 `cgas_` 前缀，改用 `chloro_` 前缀
- 用户可见描述使用中文（如"叶绿体基因组组装"）
- 新增 `analyze_chloroplast` 聚合工具，自动根据输入类型选择模块

### 3. 双细胞器通用工具

对于密码子分析、GC 分析、系统发育等，底层算法相同，差异在于：
- **基因集不同**：线粒体用 nad/cox/atp，叶绿体用 psa/psb/pet/ndh/rbcL
- **遗传密码不同**：线粒体 Table 1，叶绿体 Standard/Table 11
- **实现方式**：在工具参数中添加 `organelle` 字段（"mito" | "chloro"），根据选择加载对应基因集和遗传密码

### 4. 组装工具文献化

所有组装工具的参数设置必须基于文献证据：
- 默认参数引用 Ni et al. (2025) 的评估结果
- 工具选择提供策略说明（hifi_only / ont_only / hybrid / short_read）
- 输出报告包含文献推荐的质控指标

---

## 实施路线图

### Wave 1（本周）：线粒体模块补全 + 组装工具 ✅ 已完成
1. ✅ 注册 `线粒体组装` / `mito_assemble`（基于 Oatk/GetOrganelle/Flye，Ni et al. 2025 文献参数）
2. ✅ 注册 `叶绿体组装` / `chloro_assemble`（复用 CGAS module 1）
3. ✅ 注册 `线粒体质控` / `mito_qc`
4. ✅ 注册 `线粒体密码子分析` / `mito_codon`
5. ✅ 注册 `线粒体GC分析` / `mito_gc`
6. ✅ 注册 `线粒体系统发育` / `mito_phylogeny`
7. ✅ 叶绿体工具去 `cgas_` 前缀，改为 `chloro_` 前缀
8. ✅ 线粒体工具去 `run_` 前缀，改为 `mito_` 前缀
9. ⬜ 更新 `domain_prompts.py`：添加 `CHLOROPLAST_DOMAIN_KNOWLEDGE` 段

### Wave 2（下周）：叶绿体智能调度 + 去前缀 ✅ 已完成
1. ✅ 移除所有 `cgas_` 前缀，改用 `chloro_`
2. ✅ 新增 `analyze_chloroplast` 聚合工具（自动根据输入类型选择模块：assemble/annotate/analyze/compare/phylogeny）
3. ✅ 新增 `叶绿体IR边界分析` / `chloro_ir_boundary`（检测 JLB/JSB/JSA/JLA 连接点，四分区长度计算）
4. ✅ 扩展 `线粒体可视化` / `mito_visualize` 支持叶绿体 viz 类型（ir_quadripartite, gene_map_comparison）
5. ⬜ 更新 `domain_prompts.py`：添加 `CHLOROPLAST_DOMAIN_KNOWLEDGE` 段

### Wave 3（后续）：双细胞器统一
1. 为所有通用工具添加 `organelle` 参数
2. 新增 `compare_organelles` 双细胞器比较工具
3. 完善 Wiki 知识页（叶绿体 6 页）
4. 完善 Skills（叶绿体 annotation, ir_boundary）

---

## 参考架构

```
┌─────────────────────────────────────────────────────────────┐
│  AI Tool Registry (PhytoOrga AI)                            │
├─────────────────────────────────────────────────────────────┤
│  Universal Tools           │  线粒体 Tools      │  叶绿体 Tools│
│  ─────────────────         │  ─────────────     │  ─────────── │
│  list_workspace_files      │  线粒体注释        │  叶绿体组装  │
│  summarize_result          │  线粒体组装        │  叶绿体注释  │
│  web_search_literature     │  线粒体质控        │  叶绿体密码子│
│  search_genes              │  线粒体可视化      │  叶绿体系统发│
│  ...                       │  线粒体KaKs        │  叶绿体IR   │
│                            │  线粒体系统发育    │  ... (14个) │
│                            │  ... (16个模块)    │             │
├─────────────────────────────────────────────────────────────┤
│  叶绿体专用                 │  双细胞器通用                   │
│  ───────────────────        │  ─────────────                  │
│  叶绿体IR边界分析            │  compare_organelles             │
│  叶绿体光合作用基因          │  线粒体RNA编辑                  │
│  叶绿体ndh完整性            │  generate_report                │
└─────────────────────────────────────────────────────────────┘
```

## 预期收益

| 指标 | 当前 | 目标 |
|------|------|------|
| AI 可调用的分析工具 | 6 个 | 25+ 个 |
| 线粒体功能覆盖率 | 10% (2/18 模块) | 100% (18/18) |
| 叶绿体功能覆盖率 | 100% (CGAS 14) | 100% + 智能调度 |
| 双细胞器比较分析 | 0 | 3+ 工具 |
| 用户一句话触达分析 | 需手动指定模块 | AI 自动选择模块 |
