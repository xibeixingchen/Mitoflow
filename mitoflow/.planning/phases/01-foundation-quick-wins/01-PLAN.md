---
wave: 1
depends_on: []
files_modified:
  - src/mitoflow/models/genome.py
requirements: [BPS-01]
autonomous: true
---

# Plan 01: 环形基因组坐标工具方法

<objective>
在GenomeSequence模型中实现circular_distance()和circular_span()，为后续所有环形坐标修复提供基础。
</objective>

## Tasks

### Task 1: 添加circular_distance和circular_span方法

<read_first>
- `src/mitoflow/models/genome.py` — 当前GenomeSequence模型
</read_first>

<action>
在genome.py的GenomeSequence类中添加以下方法：

1. `circular_distance(self, a: int, b: int) -> int` — 计算环形基因组上两点a,b的最短距离（1-based坐标）。公式：`min(abs(a-b), self.length - abs(a-b))`

2. `circular_span(self, start: int, end: int) -> int` — 计算从start到end的正向跨度（1-based, inclusive）。如果end >= start: `end - start + 1`。如果end < start（跨原点）: `self.length - start + end + 1`

3. `wrap_position(self, pos: int) -> int` — 将位置归一化到[1, length]范围。公式：`((pos - 1) % self.length) + 1`

4. 添加类方法 `circular_positions_between(self, start: int, end: int) -> list[int]` — 返回start到end正向的所有位置（处理跨原点情况）

所有方法使用1-based坐标（与GenBank/MitoFlow约定一致）。
</action>

<acceptance_criteria>
- `genome.py` 包含 `def circular_distance(self, a: int, b: int) -> int`
- `genome.py` 包含 `def circular_span(self, start: int, end: int) -> int`
- `genome.py` 包含 `def wrap_position(self, pos: int) -> int`
- circular_distance(1, 500000, 500000) 返回 0 或 1
- circular_span(499000, 1000, 500000) 返回 2001 (跨原点)
- wrap_position(500001, 500000) 返回 1
</acceptance_criteria>

### Task 2: 编写环形坐标单元测试

<read_first>
- `src/mitoflow/models/genome.py` — 新添加的方法
- `tests/conftest.py` — 现有测试fixture
</read_first>

<action>
创建 `tests/test_circular_coords.py`，测试以下场景：

1. 基本距离: distance(100, 200) = 100
2. 环绕距离: distance(499000, 1000) 在500kb基因组上 = 2001
3. 正向跨度: span(100, 200) = 101 (inclusive)
4. 跨原点跨度: span(499000, 1000) = 2001
5. 边界: span(1, length) = length
6. wrap_position: 超出范围位置归一化
7. 同一点: distance(x, x) = 0

使用pytest，genome_length=500000作为测试数据。
</action>

<acceptance_criteria>
- `tests/test_circular_coords.py` 文件存在
- `pytest tests/test_circular_coords.py` 全部通过
- 覆盖跨原点和边界情况
</acceptance_criteria>

## Verification

```bash
pytest tests/test_circular_coords.py -v
python3 -c "from mitoflow.models.genome import GenomeSequence; g=GenomeSequence(seqid='test', sequence='A'*500000); print(g.circular_distance(499000, 1000)); print(g.circular_span(499000, 1000))"
```

## must_haves

- circular_distance正确处理跨原点情况
- circular_span正确处理跨原点情况
- 所有坐标使用1-based约定
- 单元测试全部通过
