<p align="center">
  <img src="docs/mitoflow_logo.png" alt="MitoFlow Logo" width="400"/>
</p>

<p align="center">
  中文 | <a href="README.md">English</a>
</p>

<p align="center">
  <em>一条命令，一篇论文。</em>
</p>

---

**MitoFlow** 是一个基于 Python 3.10+ 的植物线粒体基因组注释与比较分析平台。从原始 FASTA 到发表级输出——注释、密码子使用、选择压力、核苷酸多样性、共线性、系统发育——统一 CLI 一键完成。

## 功能特色

- **自动化注释** — 蛋白编码基因（pyhmmer HMM + BLAST）、tRNA（tRNAscan-SE + ARAGORN）、rRNA（Barrnap），支持边界校正和 RNA 编辑
- **密码子使用分析** — RSCU、ENC、GC3s、GC12、PR2 偏倚图、中性绘图、ENC-GC3s 选择绘图（7 张图表）
- **Ka/Ks 选择压力** — KaKs_Calculator-3.0（7 种方法），5 种可视化图表
- **核苷酸多样性 (Pi)** — CDS 与 IGS 区域 Pi 计算、进化热点识别
- **共线性可视化** — 基于 gbdraw 的线性图，配对 tblastx 比对链接
- **基因组图谱** — R（OGDrawR）或 Python（gbdraw）环形基因组图；50+ 配色方案
- **多构型结构** — 重复序列介导的重组预测与构型图
- **CMS 候选基因** — 新 ORF 扫描、嵌合基因检测、跨膜结构域预测
- **MTPT 检测** — 叶绿体来源片段识别与可视化
- **NUMT 检测** — 核线粒体 DNA 片段检测，RIdeogram 核型图
- **重复序列检测** — SSR 微卫星、串联重复、长分散重复
- **RNA 编辑** — C-to-U 编辑位点预测（起始密码子获得、终止密码子获得）
- **质量控制** — 五维评分体系（0–100 分）
- **系统发育流程** — 共有基因提取、MAFFT 比对、超矩阵拼接

## 快速开始

### 安装

```bash
# 核心包
pip install mitoflow

# 含 gbdraw 可视化支持
pip install "mitoflow[viz-gbdraw]"

# 外部工具（可选但推荐）
conda install -c bioconda trnascan-se aragorn barrnap blast mafft trimal iqtree

# R 可视化支持（可选，用于生成发表级 PNG/PDF/PPTX 三种格式图表）
Rscript -e "install.packages(c('ggplot2', 'eoffice'))"
# NUMT 核型图额外依赖：
Rscript -e "install.packages('RIdeogram')"
```

### 注释线粒体基因组

```bash
mitoflow annotate \
  -i mitogenome.fasta \
  -o results/ \
  --name "Arabidopsis thaliana" \
  --cp chloroplast.fasta
```

运行完整 10 步流程：加载、PCG 注释、tRNA/rRNA 注释、边界校正、CDS 验证、GFF3 + GenBank 输出、序列提取、质控、MTPT 检测。

## 下游分析

所有分析命令均支持 `--plot/--no-plot`（默认生成图表）和 `--dpi`（默认 300）选项。当 R 环境可用时，自动生成 **PNG + PDF + PPTX** 三种格式；否则使用 matplotlib 回退（仅 PNG）。

### 密码子使用分析

```bash
mitoflow codon -i annotation.gbk -o codon_results/
```

生成 7 张图表：
- **RSCU 热图** — 各基因相对 synonymous 密码子使用度
- **ENC-GC3s 基础图** — 有效密码子数与 GC3s 关系
- **ENC-GC3s 增强图** — 含标准曲线与选择区域标注
- **密码子使用柱状图** — 各密码子使用频率
- **氨基酸频率图** — 氨基酸组成分布
- **PR2 偏倚图** — A/T vs G/C 偏倚分析
- **中性绘图** — GC12 vs GC3 关系

### Ka/Ks 选择压力

```bash
mitoflow kaks -q query.gbk -r ref1.gbk -r ref2.gbk -o kaks_results/ --method MA
```

生成 5 张图表：
- **omega 柱状图** — 各基因 Ka/Ks 值
- **omega 分布图** — Ka/Ks 值箱线图
- **基因热图** — 多物种多基因选择压力热图
- **ML 散点图** — Ka vs Ks 关系散点
- **选择类型饼图** — 纯化/中性/正向选择比例

支持 7 种计算方法：MA（模型平均）、NG、LWL、LPB、GY、YN、ALL。

### 核苷酸多样性

```bash
mitoflow pi -i sp1.gbk -i sp2.gbk -o pi_results/
```

生成 3 张图表：
- **Pi 柱状图** — 各区域核苷酸多样性
- **Pi 分布图** — Pi 值频率分布
- **物种比较图** — 跨物种 Pi 对比

### MTPT 检测

```bash
mitoflow mtpt -i mito.fasta -c chloroplast.fasta -o mtpt_results/
```

检测线粒体中叶绿体来源的 DNA 片段。生成 4 张图表：
- **类别柱状图** — intact/degenerate/fragment/ancient 分布
- **一致性分布图** — MTPT 序列一致性直方图
- **线粒体覆盖图** — MTPT 在线粒体基因组上的位置与一致性散点图
- **基因覆盖图** — 被转移片段覆盖的叶绿体基因

### NUMT 检测

```bash
mitoflow numt -i mito.fasta -n nuclear.fasta -o numt_results/
```

检测核基因组中的线粒体 DNA 片段（核转移）。生成 5 张图表：
- **核型图** — RIdeogram 绘制的核染色体核型，标注 NUMT 位置标记
- **类别柱状图** — intact/partial/chimeric 分布
- **一致性直方图** — NUMT 序列一致性分布
- **线粒体覆盖图** — NUMT 在线粒体基因组上的位置散点图
- **染色体分布图** — 各核染色体上的 NUMT 数量

> 核型图需要安装 RIdeogram R 包，其他图表仅需 ggplot2 + eoffice。

### 重复序列检测

```bash
mitoflow repeat -i mitogenome.fasta -o repeat_results/
```

检测三种类型的重复序列：SSR 微卫星、串联重复、长分散重复。生成 5 张图表：
- **SSR 类别分布** — mono/di/tri/tetra/penta/hexa 分布柱状图
- **SSR 基序排名** — Top 20 高频 SSR 基序水平柱状图
- **串联重复周期** — 串联重复单元长度分布直方图
- **长重复图谱** — 线性基因组图 + 弧线连接重复对
- **长重复类型** — forward/reverse/complement/palindromic 饼图

### 多构型结构分析

```bash
mitoflow multiconf -i mitogenome.fasta -o multiconf_results/ --gbk annotation.gbk
```

预测由大重复序列介导的重组产生的主环与亚基因组构型。生成 4 张图表：
- **重复图谱** — 线性基因组图，弧线连接重复对（direct 红色 / inverted 蓝色）
- **构型图** — 主环与亚环的圆形表示
- **重组汇总** — 重复长度柱状图，按方向着色
- **类型分布饼图** — direct/inverted 比例

### CMS 候选基因预测

```bash
mitoflow cms -i mitogenome.fasta --gbk annotation.gbk -o cms_results/
```

预测细胞质雄性不育候选基因。生成 4 张图表：
- **评分分解图** — 堆叠水平柱状图，展示 chimera/tm/homolog/context/length 五维评分
- **候选热图** — 候选基因 × 评分维度热图
- **基因组上下文图** — 线性基因组图，标注候选 ORF 位置（按置信度着色）
- **置信度分布图** — High/Medium/Low 环形图

### RNA 编辑位点预测

```bash
mitoflow rna-edit -i annotation.gbk -o rna_edit_results/
```

预测 C-to-U RNA 编辑位点（起始密码子获得、终止密码子获得）。生成 3 张图表：
- **基因编辑数** — 各基因 RNA 编辑位点数柱状图
- **编辑类型饼图** — stop-gain / start-gain 比例
- **密码子位置分布** — 编辑位点在密码子第一/二/三位的位置分布

### 质量控制

```bash
mitoflow qc -i mitogenome.fasta --gbk annotation.gbk -o qc_results/
```

五维评分体系（完整性 35%、正确性 25%、连续性 15%、污染度 15%、结构 10%）。生成 3 张图表：
- **雷达图** — 五维评分蛛网图
- **仪表图** — 总分仪表盘
- **维度汇总图** — 各维度评分柱状图（含阈值线）

### 共线性分析

```bash
mitoflow synteny -i sp1.gbk -i sp2.gbk -o synteny_results/ --viz gbdraw
```

### 基因组图谱

```bash
mitoflow viz -i annotation.gbk -o genome_map.png --style gbdraw --palette orchid
```

## 可视化

### R 可视化（推荐）

安装 R 的 `ggplot2` 和 `eoffice` 包后，所有分析模块自动生成发表级图表，输出三种格式：

| 格式 | 后端 | 说明 |
|------|------|------|
| PNG | ggplot2 + ggsave | 高分辨率位图（默认 300 DPI，`--dpi` 可调） |
| PDF | ggplot2 + ggsave | 矢量图，适合论文投稿 |
| PPTX | eoffice::topptx | PowerPoint/LibreOffice 可编辑 |

安装方式：

```bash
# 基础 R 可视化（所有模块通用）
Rscript -e "install.packages(c('ggplot2', 'eoffice'))"

# NUMT 核型图额外依赖
Rscript -e "install.packages('RIdeogram')"
```

### Matplotlib 回退

若 R 不可用，所有模块自动回退到 matplotlib（仅 PNG）。无需额外安装。

### 基因组图谱后端

| 后端 | 语言 | 风格 | 安装 |
|------|------|------|------|
| **OGDrawR** | R | OGDraw 风格环形图 | `Rscript -e "remotes::install_github('xibeixingchen/OGDrawR')"` |
| **gbdraw** | Python | 发表级 SVG/PNG，50+ 配色 | `pip install gbdraw cairosvg` |

## 输出结构

```
results/
├── gff/                       # GFF3 注释
├── genbank/                   # GenBank 格式（可直接提交 NCBI）
├── fasta/                     # CDS、Protein、tRNA、rRNA、Gene、Intron
└── report/                    # 质控评分、MTPT 报告、基因组图谱
    └── plots/                 # 可视化输出（PNG/PDF/PPTX）
```

## CLI 命令

| 命令 | 说明 | 图表数 |
|------|------|--------|
| `annotate` | 完整注释流程 | — |
| `qc` | 五维质量控制 | 3 |
| `mtpt` | MTPT 检测 | 4 |
| `codon` | 密码子使用分析 | 7 |
| `kaks` | Ka/Ks 选择压力 | 5 |
| `pi` | 核苷酸多样性与热点检测 | 3 |
| `rna-edit` | RNA 编辑位点预测 | 3 |
| `numt` | NUMT 核转移检测 | 5 |
| `repeat` | SSR + 串联 + 长重复检测 | 5 |
| `multiconf` | 多构型结构预测 | 4 |
| `cms` | CMS 候选基因预测 | 4 |
| `synteny` | 共线性分析与可视化 | — |
| `phylo` | 系统发育比对准备 | — |
| `phylo-tree` | 系统发育树构建 | — |
| `viz` | 基因组图谱生成 | — |
| `report` | HTML 报告生成 | — |
| `gc` | GC 含量分析 | — |

## 内置参考数据库

- **46 个 HMM 谱** — 蛋白编码基因（多物种 MAFFT 比对构建）
- **46 个蛋白参考 FASTA** — BLAST 兜底
- **323 个基因产物** — 标准化命名
- **782 个基因别名** — 跨工具兼容
- **23 个已知 CMS 基因** — 来自 15+ 植物物种

## 引用

如在研究中使用 MitoFlow，请引用：

```
MitoFlow: A modern plant mitochondrial genome annotation and analysis platform.
```

## 许可证

[MIT](LICENSE)
