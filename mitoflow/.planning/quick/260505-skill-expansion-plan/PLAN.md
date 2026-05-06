# MitoFlow Skill 扩展计划

## 现状分析

### 当前技能（7个）
| Skill | 领域 | 状态 |
|-------|------|------|
| annotation | 线粒体注释 | 已有 |
| assembly | 线粒体组装 | 已有 |
| cms | CMS检测 | 已有 |
| comparative | 比较基因组 | 已有 |
| erc | ERC分析 | 已有 |
| karpathy-guidelines | 开发规范 | 已有 |
| qc | 质量控制 | 已有 |

### 技能格式现状
当前使用简单 Markdown 格式：Contract / Workflow / Tools / Parameters / References，无 frontmatter，无结构化元数据。

### 差距（vs Round 4 目标）
- 叶绿体技能：0个（目标 6+）
- 文献检索技能：0个（目标 3）
- 双细胞器比较：0个（目标 2）
- 系统发育/密码子/可视化：未覆盖叶绿体

---

## 参考项目设计对比

### ClawBio 格式（推荐升级方向）
```yaml
---
name: skill-name
version: 0.1.0
description: 一句话描述
author:
license: MIT
tags: [tag1, tag2]
inputs:
  - name: input1
    type: file
    format: [fasta, fastq]
    description: 输入描述
outputs:
  - name: output1
    type: file
    format: tsv
    description: 输出描述
metadata:
  category: bioinformatics
  emoji: "🧬"
  min_python: "3.10"
  dependencies: [pandas, biopython]
---
```

### ScienceClaw 格式
- 有 frontmatter（name, description）
- 详细的步骤说明和工具格式规范
- 强调 `@tool` 装饰器模式

### MitoFlow 当前格式
- 无 frontmatter
- 简单的 Contract / Workflow / 表格
- loader.py 已支持解析，但无结构化元数据

---

## 扩展计划

### Phase 1: Skill 格式升级 + 叶绿体基础技能（P0）

**1.1 升级 loader.py 支持 ClawBio 风格 frontmatter**
- 在现有解析逻辑基础上增加 YAML frontmatter 解析
- 保持向后兼容（无 frontmatter 的 skill 仍可加载）
- 新增字段：tags, inputs, outputs, metadata(category, emoji, dependencies)

**1.2 新增叶绿体注释 skill**
- 文件：`ai/skills/chloroplast_annotation/SKILL.md`
- 内容：叶绿体基因注释流程（PCG/tRNA/rRNA/IR）
- 参考：CGAS module 2，叶绿体特异性基因（psbA, rbcL, ndh*）

**1.3 新增叶绿体组装 skill**
- 文件：`ai/skills/chloroplast_assembly/SKILL.md`
- 内容：GetOrganelle/Oatk/Flye 叶绿体组装策略
- 参考：Ni et al. (2025) PBJ 综述

**1.4 新增 IR 边界分析 skill**
- 文件：`ai/skills/ir_boundary/SKILL.md`
- 内容：LSC/IRb/SSC/IRa 四分区边界检测
- 参考：JLB/JSB/JSA/JLA 连接点分析

**1.5 新增叶绿体质控 skill**
- 文件：`ai/skills/chloroplast_qc/SKILL.md`
- 内容：叶绿体基因组质量评估（IR一致性、基因完整性、重叠群）

**1.6 新增密码子分析 skill（双细胞器）**
- 文件：`ai/skills/codon_analysis/SKILL.md`
- 内容：线粒体+叶绿体密码子使用偏性、RSCU、密码子表差异
- 关键点：线粒体 Table 1 vs 叶绿体 Table 11

**1.7 新增基因组可视化 skill（双细胞器）**
- 文件：`ai/skills/genome_visualization/SKILL.md`
- 内容：pycirclize/pygenomeviz/OGDraw 使用指南
- 覆盖：环形图、线性图、共线性图

### Phase 2: 文献与知识技能（P1）

**2.1 新增文献检索 skill**
- 文件：`ai/skills/literature_search/SKILL.md`
- 内容：Google Scholar / PubMed 检索策略
- 工具：serpapi, scholarly, NCBI E-utilities

**2.2 新增论文导入 skill**
- 文件：`ai/skills/paper_import/SKILL.md`
- 内容：PDF 解析、DOI 提取、元数据标准化
- 工具：PyPDF2, pdfplumber, crossref API

**2.3 新增 Wiki 生成 skill**
- 文件：`ai/skills/wiki_generation/SKILL.md`
- 内容：从论文生成 LLM Wiki 的 prompt 模板
- 输出格式：frontmatter + Markdown 正文

**2.4 升级现有 annotation skill**
- 增加叶绿体注释子流程
- 添加双细胞器对比表格

**2.5 升级现有 assembly skill**
- 区分线粒体 vs 叶绿体组装策略
- 添加 Ni2025 PBJ 综述参数推荐

### Phase 3: 高级分析技能（P2）

**3.1 新增系统发育 skill（双细胞器）**
- 文件：`ai/skills/phylogeny/SKILL.md`
- 内容：MAFFT→trimAl→IQ-TREE 流程
- 覆盖：线粒体 PCG + 叶绿体 PCG 联合矩阵

**3.2 新增双细胞器比较 skill**
- 文件：`ai/skills/organelle_compare/SKILL.md`
- 内容：MTPT 检测、基因转移、协同进化
- 工具：blastn 互比、基因共线性

**3.3 新增 RNA 编辑 skill（双细胞器）**
- 文件：`ai/skills/rna_editing/SKILL.md`
- 内容：线粒体 C-to-U + 叶绿体 C-to-U
- 对比：线粒体 (~400-500 sites) vs 叶绿体 (~30-50 sites)

**3.4 新增 CMS 预测 skill（升级现有 cms）**
- 增加 PPR 预测、嵌合 ORF 分析
- 添加跨物种 CMS 基因比较

---

## 技术实现

### loader.py 升级
```python
class SkillSpec:
    def __init__(...):
        self._parse(content)
        self._parse_frontmatter(content)  # 新增

    def _parse_frontmatter(self, content: str) -> None:
        """Parse YAML frontmatter if present."""
        if content.startswith('---'):
            import yaml
            # 提取 frontmatter
            ...
```

### 新增技能注册
- 技能目录自动发现（现有 loader 已支持）
- 无需修改代码，创建 `SKILL.md` 即可

### 前端集成
- ToolsView 的 Skills 标签页展示所有 skills
- 按 category 过滤（mito / chloro / shared / literature）
- 点击 AI 按钮触发 skill 对应的 prompt

---

## 执行顺序

1. **先升级 loader.py**（支持 frontmatter，向后兼容）
2. **同时写 6 个叶绿体基础 skill**
3. **升级 2 个现有 skill**（annotation + assembly）
4. **写 3 个文献 skill**
5. **写 4 个高级 skill**
6. **更新前端 SkillsView** 展示分类

---

## 验收标准

- [ ] loader.py 能解析新旧两种格式
- [ ] 叶绿体分析有 ≥6 个 skill 覆盖
- [ ] 每个 skill 包含 Contract + Workflow + 命令模板
- [ ] 前端 Skills 标签页能按分类浏览
- [ ] AI 点击能正确发送 skill prompt
