# 验证脚本设计文档

## 脚本概述

`scripts/validate_against_gold_standard.py` 是基于PMGA金标准数据的MitoFlow验证脚本。

## 设计目标

1. 自动化验证流程
2. 对标PMGA论文评估标准
3. 多格式输出（CSV/JSON/Markdown）
4. 可复用于其他注释工具评估

## 架构设计

### 模块结构

```
validate_against_gold_standard.py
├── 常量定义
│   ├── CORE_PCG_41 (核心基因列表)
│   ├── STGE_GENES (起始密码子获取基因)
│   └── SPGE_GENES (终止密码子获取基因)
│
├── 数据解析函数
│   ├── normalize_gene_name() (基因名称标准化)
│   ├── parse_genbank_features() (GenBank解析)
│   └── load_corrections() (修正数据加载)
│
├── 比较函数
│   ├── compare_gene_positions() (位置差异分析)
│   ├── calculate_metrics() (指标计算)
│   └── count_error_types() (错误分类统计)
│
├── 验证函数
│   ├── validate_single_species() (单物种验证)
│   └── generate_report() (报告生成)
│
└── main() (主函数)
```

### 数据流

```
输入数据:
  ├── NCBI GenBank文件 (原始注释)
  ├── MitoFlow输出目录
  ├── PMGA修正数据 (corrections.csv)
  └── 物种列表 (species_list.csv)

处理流程:
  1. 加载修正数据 → corrections dict
  2. 读取物种列表 → species list
  3. 对每个物种:
     ├── 解析NCBI GenBank → features, genes
     ├── 解析MitoFlow输出 → features, genes
     ├── 比较基因集合 → TP/FP/FN
     ├── 分析位置差异 → diff levels
     ├── 统计错误类型 → A/B/C
     └── 汇总结果 → results list
  4. 生成报告 → CSV/JSON/MD

输出数据:
  ├── validation_summary.csv (汇总表)
  ├── validation_details.json (详细数据)
  └── validation_report.md (Markdown报告)
```

## 核心函数说明

### parse_genbank_features()

```python
def parse_genbank_features(gb_file: Path, source_name: str = "") -> Tuple[List[Dict], int]:
    """解析GenBank文件，提取所有基因特征
    
    返回:
      - features: 基因特征列表 [{type, gene, start, end, strand, product}]
      - genome_length: 基因组长度
    """
```

### compare_gene_positions()

```python
def compare_gene_positions(ncbi_features, mitoflow_features, pmga_corrections, species):
    """比较基因位置差异
    
    偏差级别分类:
      - precise: <50bp
      - small: 50-100bp
      - medium: 100-1000bp
      - large: >1000bp
    
    返回:
      - position_diffs: 位置差异列表 [{gene, ncbi_start/end, mito_start/end, diffs, level}]
    """
```

### calculate_metrics()

```python
def calculate_metrics(ncbi_genes, mitoflow_genes, core_genes):
    """计算基因检出指标
    
    对标PMGA Table S6:
      - Accuracy = (TP+TN)/(TP+FP+TN+FN)
      - Sensitivity = TP/(TP+FN)
      - Precision = TP/(TP+FP)
      - FNR = FN/(FN+TP)
      - F1 = 2*P*S/(P+S)
    
    返回:
      - metrics dict {tp, fp, fn, accuracy, sensitivity, precision, fnr, f1}
    """
```

### count_error_types()

```python
def count_error_types(ncbi_genes, mitoflow_genes, position_diffs):
    """统计三类错误数量
    
    对标PMGA论文:
      - A类: 基因检出错误 (漏检/误检)
      - B类: 起始/终止位置错误 (>50bp)
      - C类: 剪接位点错误 (>10bp且非修正基因)
    
    返回:
      - error_counts {a_errors, b_errors, c_errors, total_errors}
    """
```

## 输出格式

### validation_summary.csv

| 列名 | 说明 |
|------|------|
| species | 物种名 |
| genome_length | 基因组长度 |
| ncbi_genes_count | NCBI检出基因数 |
| mitoflow_genes_count | MitoFlow检出基因数 |
| accuracy | 准确率 |
| sensitivity | 灵敏度 |
| precision | 精确度 |
| f1 | F1-measure |
| fnr | 漏检率 |
| core_detected | 核心基因检出数 |
| a_errors | A类错误数 |
| b_errors | B类错误数 |
| c_errors | C类错误数 |
| total_errors | 总错误数 |

### validation_details.json

```json
{
  "species_name": {
    "species": "...",
    "genome_length_ncbi": 367808,
    "genome_length_mitoflow": 367808,
    "ncbi_genes": ["atp1", "nad1", ...],
    "mitoflow_genes": ["atp1", "nad1", ...],
    "metrics": {...},
    "error_counts": {...},
    "position_diffs": [
      {
        "gene": "nad1",
        "ncbi_start": 23284,
        "ncbi_end": 23824,
        "mito_start": 23284,
        "mito_end": 23821,
        "start_diff": 0,
        "end_diff": 3,
        "max_diff": 3,
        "diff_level": "precise",
        "has_pmga_correction": false
      }
    ],
    "corrections": {...}
  }
}
```

### validation_report.md

结构：
1. 整体性能汇总
2. 位置偏差统计
3. 错误类型统计
4. 各物种验证详情

## 使用示例

```bash
# 基本用法
python scripts/validate_against_gold_standard.py \
    --ncbi-dir data/gold_standard/genbank/ \
    --mitoflow-dir results/round1/mitoflow_output/ \
    --corrections data/gold_standard/corrections.csv \
    --species-list data/gold_standard/species_list.csv \
    --output results/round1/

# 查看结果
cat results/round1/validation_report.md
cat results/round1/validation_summary.csv
```

## 扩展性设计

### 可复用组件

1. `normalize_gene_name()` - 基因名称标准化
2. `parse_genbank_features()` - GenBank解析
3. `calculate_metrics()` - 指标计算
4. `count_error_types()` - 错误分类

### 扩展到其他工具

可通过修改输入参数验证其他注释工具：
- PMGA输出
- GeSeq输出
- MFannot输出
- AGORA输出

只需确保输出目录包含GenBank格式的注释文件。

---

**文档创建时间**: 2026-04-13