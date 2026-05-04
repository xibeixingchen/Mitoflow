<!-- GSD:project-start source:PROJECT.md -->
## Project

**MitoFlow Round 3 — Annotation Accuracy Improvement**

MitoFlow is a plant mitochondrial genome annotation & analysis platform (Python CLI, 17 commands, 92 source files). Round 3 focuses on improving annotation accuracy across three error dimensions: false positive gene detection (A errors), position offset (B errors), and splice site accuracy (C errors). Currently validates at F1=79.5% on 27 gold standard species; target is ≥90%.

**Core Value:** Accurate gene annotation — every gene in the right place with the right boundaries. If the annotation is wrong, all downstream analysis (QC, comparative genomics, phylogenetics) is unreliable.

### Constraints

- **Python 3.10+**: No async, all synchronous pipeline
- **Offline**: No web APIs, all tools must be local
- **Circular genomes**: Plant mitochondrial genomes are circular — coordinate math must handle wrapping
- **Backwards compatible**: Existing CLI interface must not change
- **Test before batch**: Fix one species at a time, validate, then expand
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Language & Runtime
- **Python 3.10+** (required: `>=3.10`)
- Type hints: `from __future__ import annotations` used throughout
- No async code — entirely synchronous pipeline
## Build System
- **Hatchling** (`pyproject.toml`, `[build-system]`)
- Package layout: `src/mitoflow/` (src layout)
- Entry point: `mitoflow = "mitoflow.cli:app"` (Typer CLI)
## Core Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `biopython` | >=1.79 | Sequence I/O, GenBank/FASTA parsing |
| `pyhmmer` | >=0.7 | HMM-based protein gene annotation |
| `typer` | >=0.7 | CLI framework |
| `rich` | >=12 | Terminal output formatting |
| `pandas` | >=1.5 | Data tables (codon usage, Ka/Ks) |
| `pydantic` | >=2.0 | Data models (GenomeSequence, GeneAnnotation) |
| `matplotlib` | >=3.5 | Visualization (GC, QC plots) |
| `numpy` | >=1.21 | Numerical computation |
| `jinja2` | >=3.0 | HTML report generation |
| `pycirclize` | >=0.3 | Circular genome visualization |
| `pygenomeviz` | >=0.5 | Linear/synteny genome visualization |
## Optional Dependencies
| Package | Purpose |
|---------|---------|
| `gbdraw` >=0.9.0 | OGDraw-quality circular genome maps (Python) |
| `cairosvg` | SVG rendering for gbdraw |
| `pyyaml` | Custom color scheme persistence |
| OGDrawR (R) | Alternative OGDraw visualization via R package |
## External Tools (CLI dependencies)
| Tool | Purpose | Detection |
|------|---------|-----------|
| `tRNAscan-SE` | tRNA gene prediction | Called via subprocess |
| `ARAGORN` | tRNA gene prediction (backup) | Called via subprocess |
| `Barrnap` | rRNA gene prediction | Called via subprocess |
| `BLAST+` (tblastn, makeblastdb) | Protein-to-genome alignment | Called via subprocess |
| `minimap2` | Read mapping for coverage | Called via subprocess |
| `samtools` | BAM processing | Called via subprocess |
| `KaKs_Calculator-3.0` | Ka/Ks selection pressure | Called via subprocess |
| `MAFFT` | Multiple sequence alignment | Called via subprocess |
| `trimAl` | Alignment trimming | Called via subprocess |
| `iqtree2`/`iqtree` | Phylogenetic tree building | Called via subprocess |
| `blastn` | Repeat detection, NUMT detection | Called via subprocess |
| `Rscript` | OGDrawR visualization, various R plots | Called via subprocess |
## Dev Dependencies
| Package | Purpose |
|---------|---------|
| `pytest` | Testing framework |
| `pytest-cov` | Coverage reporting |
## Configuration
- `pyproject.toml` — build config, dependencies, pytest settings
- Test paths: `tests/`
- Python path for tests: `src/`
- No linter/formatter config (no ruff, black, mypy configs)
## Data Files (Bundled)
- `hmm_profiles/pcg/` — HMM profiles for protein-coding genes
- `blast_refs/pcg/` — BLAST reference proteins
- `blast_refs/pcg_new/`, `blast_refs/pcg_v2/` — Updated reference versions
- `blast_refs/rrna/`, `blast_refs/rrna_mito/` — rRNA references
- `blast_refs/trna/` — tRNA references
- `blast_refs/exons/` — Exon reference sequences
- `gene_info/` — Gene metadata JSON (categories, aliases, products)
- `cms/` — CMS gene database
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Code Style
- **Python 3.10+** with `from __future__ import annotations` in all files
- Type hints used consistently (function signatures, model fields)
- Pydantic v2 for data models (`BaseModel`, `computed_field`)
- Dataclasses for pipeline config/results (`@dataclass`)
- Standard library `logging` with `__name__` loggers
- Rich console for user-facing output (`from rich.console import Console`)
## Naming Conventions
- **Modules**: `snake_case` directories and files (e.g., `qc_engine.py`, `boundary.py`)
- **Classes**: `PascalCase` (e.g., `GenomeSequence`, `GeneAnnotation`, `QCEngine`)
- **Functions**: `snake_case` (e.g., `load_fasta()`, `annotate_pcg()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `_DATA_DIR`, `KNOWN_CMS_GENES`)
- **CLI commands**: `kebab-case` for multi-word (e.g., `rna_edit`, `phylo-tree`)
## Module Pattern
## Error Handling
- **No exceptions for expected cases** — Functions return result objects or lists
- **Logging** for internal errors/warnings (`logger.info()`, `logger.warning()`)
- **Console output** for user-facing messages (`console.print()`)
- Subprocess failures checked with `returncode != 0`
- Pipeline returns `PipelineResult` with `warnings: list[str]`
## Data Model Patterns
- **Pydantic models** for structured data (`GenomeSequence`, `GeneAnnotation`)
- **Dataclasses** for pipeline config/results
- **1-based genomic coordinates** throughout (consistent with GenBank convention)
- **Strand enum**: `Strand.PLUS` (1) / `Strand.MINUS` (-1)
- Computed fields via `@computed_field @property` in Pydantic models
## CLI Pattern
- **Typer** framework with `app = typer.Typer()`
- Each command decorated with `@app.command()`
- Options use `typer.Option()` with `-short` and `--long` forms
- `--plot/--no-plot` toggle for visualization
- `--dpi` parameter for plot resolution (default 300)
- `--threads/-t` for parallelism
- Common parameters: `-i/--input`, `-o/--output`, `-n/--name`
## Import Pattern
## Visualization Conventions
- Dual visualization: Python (`visualize.py`) + R (`visualize_r.py`)
- R visualization invoked via `subprocess` calling `Rscript`
- Output formats: PNG (default), SVG, PDF
- DPI configurable via `--dpi` flag
- Plot functions return `dict[str, Path]` mapping plot type to file path
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern
## Layers
```
```
## Data Flow (Annotation Pipeline)
```
```
## Module Independence
## Key Abstractions
- **`GenomeSequence`** (`models/genome.py`) — Pydantic model with computed fields for length, GC%, reverse complement
- **`GeneAnnotation`** (`models/gene.py`) — Pydantic model with exon list, strand, confidence scores
- **`DBManager`** (`db/manager.py`) — Centralized reference data access with caching (`@lru_cache`)
- **`OutputManager`** (`core/output.py`) — Lazy directory creation for output files
- **`PipelineConfig`** / **`PipelineResult`** (`core/pipeline.py`) — Dataclass configuration and results
## Entry Points
## Visualization Architecture
- **Python plots** (`visualize.py`) — matplotlib-based, cross-platform
- **R plots** (`visualize_r.py`) — R/ggplot2-based, higher quality but requires R
- **viz/** module — Specialized genome visualization (circular maps via pycirclize/gbdraw/pygenomeviz)
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| openspec-apply-change | Implement tasks from an OpenSpec change. Use when the user wants to start implementing, continue implementation, or work through tasks. | `.claude/skills/openspec-apply-change/SKILL.md` |
| openspec-archive-change | Archive a completed change in the experimental workflow. Use when the user wants to finalize and archive a change after implementation is complete. | `.claude/skills/openspec-archive-change/SKILL.md` |
| openspec-explore | Enter explore mode - a thinking partner for exploring ideas, investigating problems, and clarifying requirements. Use when the user wants to think through something before or during a change. | `.claude/skills/openspec-explore/SKILL.md` |
| openspec-propose | Propose a new change with all artifacts generated in one step. Use when the user wants to quickly describe what they want to build and get a complete proposal with design, specs, and tasks ready for implementation. | `.claude/skills/openspec-propose/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

## AI Multi-Agent Platform Reference Projects

MitoFlow AI 平台开发过程中参考了以下开源项目：

| 项目 | 仓库 | 借鉴内容 |
|------|------|----------|
| **DeepAgents** (LangChain) | `github.com/langchain-ai/deepagents` | LangGraph 状态机、子 Agent 委派 (`task`)、planning middleware |
| **ClawBio** | `github.com/ClawBio/ClawBio` | SKILL.md 规格优先设计、58 个生物信息技能、Galaxy Bridge |
| **BioClaw** | `github.com/Runchuan-BU/BioClaw` | 会话隔离、容器沙箱、自动 Notebook 导出 |
| **STELLA** | `github.com/zaixizhang/STELLA` | Manager/Dev/Critic 三 Agent 模式、Tool Ocean、OpenRouter 网关 |
| **ScienceClaw** | `github.com/AgentTeam-TaichuAI/ScienceClaw` | Vue 3 聊天 UI、MongoDB 会话存储、模型设置面板 |

### 本地克隆位置

```bash
/home/jiazc/software/deepagents    # LangGraph agent framework
/home/jiazc/software/ClawBio       # Bioinformatics skill library
/home/jiazc/software/ScienceClaw   # Vue 3 + FastAPI science agent
/home/jiazc/software/STELLA        # Biomedical multi-agent system
```

### MitoFlow AI 架构决策

- **Provider 适配**：自研 `OpenAIChatAdapter` + `AnthropicAdapter`，支持 13 个大模型
- **工具注册**：22 个工具，4 级安全分类（read_only / writes_output / launches_job / external_network）
- **Web 前端**：FastAPI 直出 HTML5 单页应用，紫色→绿色渐变主题
- **会话持久**：JSONL 消息 + JSON 元数据，重启不丢失
- **工作空间**：每 session 独立目录，分析结果自动关联
