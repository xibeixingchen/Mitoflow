---
wave: 1
depends_on: []
files_modified:
  - scripts/validate_against_gold_standard.py
requirements: [BPS-04]
autonomous: true
---

# Plan 02: 验证脚本环形距离修复

<objective>
修改验证脚本的位置比较逻辑，使用环形距离替代线性距离。这能立即减少大量B类错误（很多大偏差是度量误差）。
</objective>

## Tasks

### Task 1: 修改验证脚本使用环形距离

<read_first>
- `scripts/validate_against_gold_standard.py` — 当前验证脚本
</read_first>

<action>
1. 在validate_against_gold_standard.py中，找到计算基因位置偏差的函数
2. 将线性距离计算 `abs(mito_pos - gold_pos)` 替换为环形距离：
   ```python
   genome_length = len(genome_sequence)  # 需要获取基因组长度
   offset = min(abs(mito_pos - gold_pos), genome_length - abs(mito_pos - gold_pos))
   ```
3. 确保在加载FASTA/GenBank时提取genome_length
4. 在报告输出中标注使用了环形距离（"使用环形距离比较"）
5. 保持偏差分类阈值不变: <50bp精确, 50-100bp小偏差, 100-1000bp中偏差, >1000bp大偏差
</action>

<acceptance_criteria>
- `validate_against_gold_standard.py` 包含 `genome_length` 变量用于距离计算
- 位置偏差计算使用 `min(abs(a-b), genome_length - abs(a-b))` 形式
- 报告输出包含环形距离标注
- 能成功运行: `python scripts/validate_against_gold_standard.py --help`
</acceptance_criteria>

### Task 2: 生成Round 2基准（环形距离重算）

<read_first>
- `scripts/validate_against_gold_standard.py` — 修改后的脚本
- `results/round2/` — Round 2结果
</read_first>

<action>
1. 运行修改后的验证脚本，生成Round 2基准结果（用环形距离）
2. 保存结果到 `results/round2_circular_baseline/`
3. 比较新旧B-error数量，记录环形距离修复带来的改进
4. 这一步的目的是建立真实基线 — 区分度量误差和注释误差
</action>

<acceptance_criteria>
- `results/round2_circular_baseline/` 目录存在
- 包含验证报告，B-error数量少于Round 2原始结果
- 报告中区分了"度量改进"vs"真实注释改进"
</acceptance_criteria>

## Verification

```bash
python scripts/validate_against_gold_standard.py --help
```

## must_haves

- 位置比较使用环形距离
- 生成环形距离基准报告
- 不影响A类和C类错误计算
