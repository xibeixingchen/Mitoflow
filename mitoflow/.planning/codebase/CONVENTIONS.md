# Conventions — MitoFlow

**Mapped:** 2026-04-14

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

Each analysis module follows a consistent structure:

```python
# detector.py / predictor.py / analysis.py — Core logic
# visualize.py — Python (matplotlib) visualization
# visualize_r.py — R (ggplot2) visualization
# __init__.py — Public API exports
```

Typical module API:
```python
def detect_X(...) -> XResult:         # Core computation
def write_X_output(result, ...) -> dict:  # Write output files
def plot_all_X(result, ...) -> dict:     # Visualization
```

Result objects provide a `.summary()` method returning formatted string.

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

```python
# Relative imports within package
from ..models.genome import GenomeSequence
from ..db.manager import DBManager

# Lazy imports in CLI to avoid loading heavy dependencies
def command_handler():
    from .module.submodule import function  # Import at call time
```

CLI uses **lazy imports** — heavy modules imported inside command handlers, not at module level.

## Visualization Conventions

- Dual visualization: Python (`visualize.py`) + R (`visualize_r.py`)
- R visualization invoked via `subprocess` calling `Rscript`
- Output formats: PNG (default), SVG, PDF
- DPI configurable via `--dpi` flag
- Plot functions return `dict[str, Path]` mapping plot type to file path
