# 金标准物种数据说明

## 数据来源

数据提取自PMGA论文补充材料（Plant Communications, 2025）：
- 文件路径: `/home/jiazc/data16t/mito_genome/PMGA/PMGA_tools/pmga_supplement/1-s2.0-S2590346224006126-mmc3.xlsx`
- Table S1: 350个物种信息，其中29个Dataset 1物种有RNA-seq验证
- Table S2: 1719条exon记录，包含120+修正条目

## 数据集结构

### Dataset 1物种（29个）

具有RNA-seq验证数据的高质量物种，其线粒体基因组注释经过RNA-seq比对修正。

| 物种数 | GenBank编号 | SRA编号 | 修正数 |
|--------|-------------|---------|--------|
| Arabidopsis_thaliana | NC_037304.1 | SRR8511570 | 0（负对照） |
| Camellia_sinensis | MK574876.1, MK574877.1 | SRR13425452 | 32（最大） |
| Liriodendron_tulipifera | NC_021152.1 | SRR9849700, SRR9849652, SRR16546803 | 4 |
| Gossypium_hirsutum | NC_027406.1 | SRR16902665 | 25 |
| Nicotiana_tabacum | MN651324.1 | SRR8706334 | 3 |

完整物种列表见: `data/gold_standard/species_list.csv`

### 修正类型统计

| 修正类型 | 说明 | 数量 |
|----------|------|------|
| SSE (Splicing Site Errors) | 剪接位点位置错误 | 56 |
| STGE (Start-Gain Errors) | RNA编辑创造的起始密码子错误 | 8 |
| SPGE (Stop-Gain Errors) | RNA编辑创造的终止密码子错误 | 25 |
| Correct | 无需修正（正确注释） | 1153 |
| **总计** | | **1242** |

完整修正记录见: `data/gold_standard/corrections.csv`

## 修正详情字段说明

``corrections.csv`` 字段：

| 字段名 | 说明 |
|--------|------|
| pcg_id | 蛋白编码基因ID |
| exon_id | 外显子ID |
| species | 物种名 |
| genbank | GenBank编号 |
| gene | 基因名 |
| strand | 链方向 (+/-) |
| position_before | 修正前位置（NCBI原始） |
| position_after | 修正后位置（PMGA修正） |
| correction_type | 修正类型（SSE/STGE/SPGE/correct） |
| correction_note | 修正说明（含SSE编号） |

## 重点修正基因

修正数量最多的基因（按物种汇总）：

| 基因 | 修正数 | 主要修正类型 | 涉及物种数 |
|------|--------|--------------|-----------|
| nad1 | 15 | SSE | 8 |
| nad5 | 12 | SSE | 8 |
| ccmFC | 11 | SSE, SPGE | 8 |
| nad7 | 8 | SSE | 5 |
| atp6 | 7 | SPGE | 8 |
| cox2 | 5 | SSE | 4 |

## 验证策略建议

### 优先验证物种（5个）

1. **Arabidopsis_thaliana**: 标准参考，无修正（负对照）
2. **Camellia_sinensis**: 最大修正数（32），综合测试剪接位点、起始/终止密码子
3. **Liriodendron_tulipifera**: PCR验证10个基因
4. **Gossypium_hirsutum**: 多外显子基因测试（25修正）
5. **Nicotiana_tabacum**: 已在现有测试集，便于对比

### 重点测试基因

需要关注MitoFlow在这些基因上的表现：
- nad1, nad5: 多外显子，剪接位点易错
- ccmFC: 常见SSE和SPGE错误
- atp6: RNA编辑相关终止密码子问题
- rpl16, rps1: 已识别的位置偏差问题

## RNA-seq数据下载

使用SRA编号从NCBI下载原始RNA-seq数据：

```bash
# 示例：下载拟南芥RNA-seq
prefetch SRR8511570
fastq-dump SRR8511570 --split-files

# 批量下载脚本
for sra in SRR8511570 SRR13425452 SRR9849700 SRR16902665; do
    prefetch $sra && fastq-dump $sra --split-files
done
```

## 参考文献

Li et al. (2025). PMGA: A plant mitochondrial genome annotator. 
Plant Communications, 6, 101191.
DOI: 10.1016/j.xplc.2024.101191

---

**文档创建时间**: 2026-04-13
**数据提取时间**: 2026-04-13