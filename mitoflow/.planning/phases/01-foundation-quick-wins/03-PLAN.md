---
wave: 2
depends_on: ["01"]
files_modified:
  - src/mitoflow/annotate/trans_splicing.py
requirements: [CSP-01]
autonomous: false
---

# Plan 03: nad4系统性36bp偏移修复

<objective>
排查并修复nad4在15个物种中一致出现36bp偏移的bug。36bp=12codons，极可能是密码子相位或外显子边界计算错误。
</objective>

## Tasks

### Task 1: 定位nad4偏移根因

<read_first>
- `src/mitoflow/annotate/trans_splicing.py` — 外显子合并逻辑
- `src/mitoflow/annotate/boundary.py` — 边界校正逻辑
- `results/round2/validation_details.json` — nad4的具体偏移数据
</read_first>

<action>
1. 从validation_details.json中提取nad4在所有物种的偏移数据：
   - 偏移方向（全部是+36还是-36？）
   - 偏移位置（起始还是终止？）
   - 受影响的外显子编号

2. 检查trans_splicing.py中nad4的配置：
   ```python
   "nad4": {"exons": 4, ...}
   ```
   确认期望外显子数是否正确

3. 检查exon边界refinement函数：
   - `refine_exon_boundaries_with_codons()` 中是否有nad4特殊处理
   - 密码子相位计算是否在nad4上有off-by-one

4. 检查boundary.py中是否有nad4特殊逻辑导致36bp偏移

5. 对比一个具体物种（如Arabidopsis thaliana）的nad4 MitoFlow注释 vs NCBI注释，找出36bp差异的确切位置
</action>

<acceptance_criteria>
- 明确记录36bp偏移的根因（哪个函数、哪一行代码导致）
- 记录是起始位置偏移还是终止位置偏移
- 记录是哪个外显子的边界计算有误
</acceptance_criteria>

### Task 2: 修复nad4偏移

<read_first>
- `src/mitoflow/annotate/trans_splicing.py` — Task 1定位的问题代码
- `src/mitoflow/annotate/boundary.py` — 如果问题在此文件
</read_first>

<action>
根据Task 1的根因分析进行修复。可能的修复方向：

1. 如果是refine_exon_boundaries_with_codons中密码子搜索偏移：修正搜索起始位置
2. 如果是外显子合并时相位计算错误：修正相位计算
3. 如果是边界校正中短内含子合并导致：调整nad4的短内含子阈值

修复后运行单物种验证（Arabidopsis thaliana），确认nad4偏移消失。
</action>

<acceptance_criteria>
- Arabidopsis thaliana的nad4偏移从36bp变为0或<10bp
- nad4的外显子数正确（4个外显子）
- 不影响其他基因的注释
</acceptance_criteria>

## Verification

```bash
# 单物种快速验证
mitoflow annotate -i data/gold_standard/fasta/Arabidopsis_thaliana.fasta -o /tmp/nad4_test -n Arabidopsis_thaliana
# 检查GFF中nad4的起始/终止位置
grep nad4 /tmp/nad4_test/gff/Arabidopsis_thaliana.gff
```

## must_haves

- nad4在Arabidopsis中的36bp偏移消失
- 根因分析文档记录在PLAN.md中
- 修复不影响其他多外显子基因(nad1/nad2/nad5/nad7)
