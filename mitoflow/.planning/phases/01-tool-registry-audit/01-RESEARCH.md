# Phase 01: Tool Registry Audit - Research

**Researched:** 2026-05-06
**Domain:** MitoFlow AI Tool Registration & Execution Pipeline
**Confidence:** HIGH

## Summary

The MitoFlow AI backend maintains a unified tool registry (`ToolRegistry`) that serves CLI, API, and Web entry points. Tools are registered as `(ToolDefinition, ToolExecutor)` pairs across 9 registration modules. Currently **58 tools** are registered: **57 real executors** and **1 placeholder** (`delegate_task`). The execution pipeline flows from Web API (FastAPI SSE) through `AIService` → `DeepAgentRuntime` → `ToolRegistry.execute()` → individual executor functions, which either call internal Python APIs or subprocess-out to external tools (CGAS, assemblers, IQ-TREE).

**Primary recommendation:** The registry is well-structured but has gaps where 10+ CLI modules lack AI tool wrappers, 3 skill executors are un-wired, and one test references an outdated tool name. Prioritize adding AI tools for high-value modules (mtpt, rna_edit, cms, repeat, numt) and fixing the skill routing.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic v2 | >=2.0 | ToolDefinition, ToolContext models | Type-safe schema validation |
| Typer | >=0.7 | CLI commands | Standard Python CLI framework |
| FastAPI | latest | Web API + SSE streaming | Async-native, OpenAPI auto-gen |
| BioPython | >=1.79 | GenBank/FASTA parsing in executors | De facto bioinformatics standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyMuPDF (fitz) | optional | PDF text extraction for RAG | When literature_fetch indexes PDFs |
| pdfplumber | optional | PDF fallback extraction | When fitz unavailable |
| scholarly/serpapi | optional | Google Scholar search | When SCHOLAR_API_KEY is set |

**Installation:**
```bash
pip install pydantic typer fastapi biopython
# Optional
pip install pymupdf pdfplumber
```

## Architecture Patterns

### Recommended Tool Registration Flow
```
src/mitoflow/ai/
├── mitoflow_tools.py      # Orchestrator: calls all register_* functions
├── tools.py               # ToolRegistry + ToolContext + validation
├── models.py              # ToolDefinition, ToolCall, ToolResult, SafetyLevel
├── knowledge_tools.py     # Gene lookup, search, categories
├── skills_tools.py        # Skill registry + execution routing
├── mcp/mcp_tools.py       # MCP server wrappers
├── wiki/wiki_tools.py     # Wiki search + ingestion
├── web_tools.py           # Web search, GitHub, page fetch
├── scholar_tools.py       # Google Scholar SerpAPI
├── cgas_tools.py          # Chloroplast module wrappers (CGAS subprocess)
├── runtime_deep.py        # DeepAgentRuntime + delegate_task placeholder
└── service.py             # AIService: entry point for all callers
```

### Pattern 1: Closure-Based Executor Factory (CGAS)
**What:** `_make_executor(module_num)` returns a closure that calls `_run_chloro_module()` with the correct module number.
**When to use:** When registering multiple similar tools that differ only by a parameter (e.g., 14 chloroplast modules).
**Example:**
```python
# Source: src/mitoflow/ai/cgas_tools.py
def _make_executor(module_num: int):
    def _executor(exec_args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        result = _run_chloro_module(module_num, cmd_args, work_dir)
        ...
    return _executor
```

### Pattern 2: Auto-Resolve Input Paths
**What:** `_resolve_input_path()` checks session workspace first, then workspace root, then treats as absolute.
**When to use:** All file-based tool executors.
**Example:**
```python
# Source: src/mitoflow/ai/mitoflow_tools.py
def _resolve_input_path(input_arg: str, context: ToolContext) -> Path:
    p = Path(input_arg)
    if not p.is_absolute():
        session_ws = context.workspace_root / context.session_id
        candidate = session_ws / input_arg
        if candidate.exists():
            p = candidate
        else:
            p = ensure_under_root(input_arg, context.workspace_root)
    return p
```

### Pattern 3: Anti-Loop Protection
**What:** Track identical consecutive tool failures and abort after MAX_SAME_FAILURE (3).
**When to use:** All runtime loops (DeepAgentRuntime and SSE stream).
**Example:**
```python
# Source: src/mitoflow/ai/runtime_deep.py + routes/ai.py
fail_key = f"{call.name}:{json.dumps(call.arguments, sort_keys=True)}"
_failure_tracker[fail_key] = _failure_tracker.get(fail_key, 0) + 1
if _failure_tracker[fail_key] >= MAX_SAME_FAILURE:
    # Abort with error message
```

### Anti-Patterns to Avoid
- **Hard-coding paths:** CGAS path uses `../../CGAS` relative to file location — fragile if package is moved.
- **Silent exception swallowing:** Multiple `except Exception: pass` blocks in RAG/literature fetch hide real errors.
- **Mixed entry_point enforcement:** Some tools register for CLI/API but not WEB without clear rationale.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON Schema validation | Custom parser | `_validate_args()` in `tools.py` | Already handles required, types, basic validation |
| Path traversal protection | Manual checks | `ensure_under_root()` | Resolves and validates path containment |
| Tool registry | Dicts in module | `ToolRegistry` class | Supports entry_point filtering, duplicate detection |
| Session storage | Raw JSON files | `LocalSessionStore` | Handles messages, events, artifacts atomically |

## Common Pitfalls

### Pitfall 1: Missing AI Tools for CLI Modules
**What goes wrong:** 10 CLI commands have no corresponding AI tool, so the agent cannot invoke them.
**Why it happens:** AI tools were added incrementally; some modules (mtpt, rna_edit, cms, etc.) were never wrapped.
**How to avoid:** Create `mito_*` wrappers for all CLI commands, following the `mito_annotate` pattern.
**Warning signs:** User asks "analyze MTPT" and agent responds with generic text instead of running analysis.

### Pitfall 2: Unwired Skill Executors
**What goes wrong:** `SKILL_EXECUTORS` maps 6 skills but `execute_skill()` only wires 3 (`annotation`, `qc`, `cms`).
**Why it happens:** Skills were defined but routing code was never completed for `erc`, `comparative`, `assembly`.
**How to avoid:** Add `if runner_name == ...` branches or refactor to a dispatch table.

### Pitfall 3: Outdated Test References
**What goes wrong:** `test_ai_service.py` asserts `"run_annotation" in names` but the tool is named `mito_annotate`.
**Why it happens:** Tool was renamed but test was not updated.
**How to avoid:** Search for old tool names when renaming.

### Pitfall 4: CGAS Backend Path Fragility
**What goes wrong:** `_CGAS_DIR` uses `Path(__file__).resolve().parent.parent.parent.parent.parent / "CGAS"` — breaks if installed as package.
**Why it happens:** Assumes development directory layout.
**How to avoid:** Make CGAS path configurable via environment variable.

### Pitfall 5: RAG Dependencies Not Installed
**What goes wrong:** `web_search_literature` imports `RAGRetriever` but catches all exceptions silently. If embeddings/vector store backends fail, user gets no indication.
**Why it happens:** `except Exception: pass` in multiple places.
**How to avoid:** Log warnings at minimum; surface RAG availability status to user.

## Code Examples

### Registering a New Tool
```python
# Source: src/mitoflow/ai/mitoflow_tools.py (pattern)
registry.register(
    ToolDefinition(
        name="my_tool",
        description="What this tool does.",
        parameters={
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input file path."},
            },
            "required": ["input"],
            "additionalProperties": False,
        },
        safety_level=SafetyLevel.READ_ONLY,
        entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
    ),
    my_tool_executor,
)
```

### Executing a Tool from API
```python
# Source: deploy/web/backend/routes/ai.py
ctx = ToolContext(
    session_id=sid,
    workspace_root=svc.workspace_root,
    output_root=store.artifact_dir(sid),
    entry_point=EntryPoint.API,
    last_user_message=req.message,
)
result = svc.registry.execute(tc, ctx)  # tc: ToolCall
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Simple AgentRuntime loop | DeepAgentRuntime with planning + delegation | Round 4 | Better multi-step reasoning, sub-agent support |
| Only mitochondrial tools | Dual organelle (mito + chloro) | Round 4 | 14 new chloro modules via CGAS |
| Manual tool registration | Modular register_* functions | Round 3 | Cleaner separation of concerns |

**Deprecated/outdated:**
- `run_annotation` tool name: replaced by `mito_annotate`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | CGAS backend exists at `../../CGAS` relative to project root | cgas_tools.py | Chloroplast tools fail if path is wrong |
| A2 | `SCHOLAR_API_KEY` env var enables Google Scholar search | scholar_tools.py | Scholar tools return "key not set" message |
| A3 | RAG vector store and embeddings are optional (graceful degradation) | web_tools.py | Literature search falls back to CrossRef |

## Open Questions

1. **Should `delegate_task` remain a placeholder?**
   - What we know: DeepAgentRuntime intercepts `delegate_task` calls and routes to `_run_sub_agent()`.
   - What's unclear: Whether the placeholder executor should ever be called directly.
   - Recommendation: Keep placeholder; actual logic is in runtime.

2. **Should all 18 CLI modules have AI tool wrappers?**
   - What we know: Only 7 have wrappers (annotate, qc, codon, gc, assemble, phylogeny, visualize).
   - What's unclear: Priority order for the remaining 10.
   - Recommendation: High priority: mtpt, rna_edit, cms, repeat, numt. Low: db, extract.

3. **Should CGAS path be configurable?**
   - What we know: Currently hardcoded relative path.
   - What's unclear: Whether CGAS will be installed as a package or always side-by-side.
   - Recommendation: Add `CGAS_DIR` environment variable fallback.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | All | Yes | 3.11 | — |
| CGAS backend | chloro_* tools | Unknown | — | Skip chloroplast analysis |
| Oatk/Flye/GetOrganelle | mito_assemble | Unknown | — | Return "not installed" error |
| IQ-TREE | phylo-tree CLI | Unknown | — | Skip tree building |
| SCHOLAR_API_KEY | scholar_* tools | Unknown | — | Return "set API key" message |
| PyMuPDF/pdfplumber | literature_fetch | Unknown | — | Skip PDF indexing |

**Missing dependencies with no fallback:**
- None — all tools gracefully degrade or return informative errors.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml |
| Quick run command | `pytest tests/test_ai_service.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REG-01 | All registered tools have executors | unit | `pytest tests/test_ai_tools.py -x` | ❌ Wave 0 |
| REG-02 | No duplicate tool names | unit | `pytest tests/test_ai_tools.py -x` | ❌ Wave 0 |
| REG-03 | CLI-AI tool mapping consistency | unit | `pytest tests/test_ai_cli_mapping.py -x` | ❌ Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_ai_tools.py` — comprehensive tool registry tests
- [ ] Fix `tests/test_ai_service.py:14` — change `run_annotation` to `mito_annotate`
- [ ] Add test for skill executor wiring (all 6 skills)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `_validate_args()` JSON schema validation |
| V5 Path Traversal | yes | `ensure_under_root()` path containment |
| V6 Cryptography | no | No crypto in this phase |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via tool args | Tampering | `ensure_under_root()` resolves and validates |
| Tool enumeration | Information Disclosure | EntryPoint filtering limits exposure |
| Infinite tool loops | Denial of Service | Anti-loop tracker (max 3 same failures) |

## Sources

### Primary (HIGH confidence)
- `src/mitoflow/ai/mitoflow_tools.py` — 11 direct registrations + 8 sub-register calls
- `src/mitoflow/ai/tools.py` — ToolRegistry class, validation, execution
- `src/mitoflow/ai/cgas_tools.py` — 14 chloroplast module registrations
- `src/mitoflow/ai/service.py` — AIService, build_default_registry
- `deploy/web/backend/routes/ai.py` — FastAPI SSE execution pipeline
- `src/mitoflow/cli.py` — 21 CLI commands

### Secondary (MEDIUM confidence)
- `src/mitoflow/ai/skills_tools.py` — SKILL_EXECUTORS mapping
- `src/mitoflow/ai/rag/retriever.py` — Three-layer search architecture
- `src/mitoflow/ai/literature_fetch.py` — Auto-fetch pipeline

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from pyproject.toml and source
- Architecture: HIGH — verified from complete source read
- Pitfalls: HIGH — verified by grep and runtime analysis

**Research date:** 2026-05-06
**Valid until:** 2026-06-06 (stable codebase)
