"""Allowlisted MitoFlow tools for AI orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .models import EntryPoint, SafetyLevel, ToolDefinition
from .tools import ToolContext, ToolRegistry, ensure_under_root


MITOFLOW_MODULES: List[str] = [
    "annotate",
    "qc",
    "viz",
    "mtpt",
    "rna-edit",
    "codon",
    "multiconf",
    "kaks",
    "synteny",
    "pi",
    "phylo",
    "cms",
    "validate-rna",
    "report",
    "repeat",
    "numt",
    "gc",
    "phylo-tree",
]


def register_mitoflow_tools(registry: ToolRegistry) -> None:
    """Register the first safe MitoFlow AI tools."""
    from .knowledge_tools import register_knowledge_tools
    register_knowledge_tools(registry)

    from .mcp.mcp_tools import register_mcp_tools
    register_mcp_tools(registry)

    from .wiki.wiki_tools import register_wiki_tools
    register_wiki_tools(registry)

    from .skills_tools import register_skills_tools
    register_skills_tools(registry)

    from .runtime_deep import register_deep_agent_tools
    register_deep_agent_tools(registry)

    from .web_tools import register_web_tools
    register_web_tools(registry)

    registry.register(
        ToolDefinition(
            name="list_mitoflow_modules",
            description="List currently available MitoFlow analysis modules.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        list_mitoflow_modules,
    )
    registry.register(
        ToolDefinition(
            name="summarize_result_directory",
            description="Inspect a MitoFlow result directory and summarize known output files.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path under the configured workspace root."}
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        summarize_result_directory,
    )
    registry.register(
        ToolDefinition(
            name="run_annotation",
            description="Run MitoFlow annotation on a FASTA file. Use path from list_workspace_files output. Works with uploaded files directly.",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Path to FASTA file."},
                    "name": {"type": "string", "description": "Annotation project name."},
                    "threads": {"type": "integer", "minimum": 1, "maximum": 16},
                    "skip_trna": {"type": "boolean"},
                    "skip_rrna": {"type": "boolean"},
                    "skip_qc": {"type": "boolean"},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.LAUNCHES_JOB,
            entry_points=[EntryPoint.CLI, EntryPoint.API],
        ),
        run_annotation,
    )


    registry.register(
        ToolDefinition(
            name="run_visualization",
            description=(
                "Generate visualization plots for a mitochondrial genome. "
                "Supports circular genome maps (pycirclize), linear genome maps (pygenomeviz), "
                "and OGDraw-quality maps (gbdraw). Input is an annotated GenBank file."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "genbank_file": {"type": "string", "description": "Path to annotated GenBank (.gb) file."},
                    "viz_type": {"type": "string", "enum": ["circular", "linear", "ogdraw", "gc"], "description": "circular/linear/ogdraw/gc"},
                },
                "required": ["genbank_file"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.WRITES_OUTPUT,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        run_visualization,
    )
    registry.register(
        ToolDefinition(
            name="list_workspace_files",
            description=(
                "List files in the current session workspace. Use this FIRST whenever "
                "a user asks to run analysis on 'my data' or 'uploaded files'. "
                "Returns file names, types, and sizes. Supports filtering by extension."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filter": {"type": "string", "description": "Optional file extension filter (e.g. '.fasta', '.gb'). Leave empty to list all."},
                },
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        list_workspace_files,
    )


def list_workspace_files(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """List files in the current session workspace only."""
    ext_filter = args.get("filter", "")
    from pathlib import Path as _Path

    # Use the session-specific workspace directory
    ws = _Path("./mitoflow_workspace") / context.session_id
    if not ws.exists():
        ws = _Path("/home/jiazc/data16t/mito_genome/PMGA/mitoflow/mitoflow_workspace") / context.session_id

    files = []
    for p in sorted(ws.rglob("*")) if ws.exists() else []:
        if p.is_file():
            if ext_filter and not p.suffix.lower() == ext_filter.lower():
                continue
            files.append({
                "name": p.name,
                "path": str(p),
                "size": p.stat().st_size,
                "type": p.suffix.lower(),
            })

    if not files:
        content = "No files found in your workspace. Upload files via the Workspace tab (📁) or use the 📎 button in the chat input."
    else:
        lines = [f"Your workspace has {len(files)} file(s):"]
        for f in files[:20]:
            sz = f"{f['size']/1024:.1f}KB" if f['size'] < 1048576 else f"{f['size']/1048576:.1f}MB"
            lines.append(f"- {f['name']} ({sz}, {f['type']})")
        content = "\n".join(lines)
    return {"content": content, "data": {"files": files[:20], "workspace": str(ws)}}


def run_visualization(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Generate visualization plots for a mitochondrial genome."""
    from pathlib import Path as _Path
    input_arg = args["genbank_file"]
    gb_path = _Path(input_arg)
    if not gb_path.is_absolute():
        session_ws = _Path("./mitoflow_workspace") / context.session_id
        candidate = session_ws / input_arg
        if candidate.exists():
            gb_path = candidate
        else:
            # Check annotation artifacts
            art_ws = _Path("./.mitoflow_ai_sessions") / context.session_id / "artifacts"
            for cand in art_ws.rglob(input_arg):
                gb_path = cand; break
    if not gb_path.exists():
        return {"content": f"GenBank file not found: {input_arg}", "data": {}}

    viz_type = args.get("viz_type", "circular")
    output_dir = _Path("./mitoflow_workspace") / context.session_id / "viz"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    try:
        if viz_type == "circular":
            from ..viz.circos_plot_v2 import plot_mito_genome
            out = output_dir / f"{gb_path.stem}_circular.png"
            plot_mito_genome(str(gb_path), genome_name=gb_path.stem, output_file=str(out))
            results.append({"type": "circular", "file": str(out), "name": out.name})

        elif viz_type == "linear":
            from ..viz.linear import draw_linear_genome
            out = output_dir / f"{gb_path.stem}_linear.png"
            draw_linear_genome(gb_path, str(out))
            results.append({"type": "linear", "file": str(out), "name": out.name})

        elif viz_type == "ogdraw":
            from ..viz.gbdraw_plot import check_gbdraw_available, draw_with_gbdraw
            if check_gbdraw_available():
                out = output_dir / f"{gb_path.stem}_ogdraw.png"
                draw_with_gbdraw(gb_path, str(out))
                results.append({"type": "ogdraw", "file": str(out), "name": out.name})
            else:
                return {"content": "gbdraw package is not available. Install with: pip install gbdraw", "data": {}}

        elif viz_type == "gc":
            from ..viz.gc_content import plot_gc_profile
            out = output_dir / f"{gb_path.stem}_gc.png"
            from Bio import SeqIO
            rec = SeqIO.read(str(gb_path), "genbank")
            plot_gc_profile(str(rec.seq), window=200, output_path=str(out), title=f"{gb_path.stem} GC Profile")
            results.append({"type": "gc", "file": str(out), "name": out.name})

        return {
            "content": f"Generated {len(results)} visualization(s):\n" + "\n".join(
                f"- {r['type']}: {r['name']}" for r in results
            ),
            "data": {"visualizations": results, "output_dir": str(output_dir)},
        }
    except Exception as e:
        return {"content": f"Visualization failed: {e}", "data": {}}


def list_mitoflow_modules(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Return module names and a compact summary."""
    return {
        "content": "Available MitoFlow modules: " + ", ".join(MITOFLOW_MODULES),
        "data": {"modules": MITOFLOW_MODULES},
    }


def summarize_result_directory(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Summarize known files under a MitoFlow output directory."""
    path = ensure_under_root(args["path"], context.workspace_root)
    if not path.exists():
        raise FileNotFoundError(path)
    if not path.is_dir():
        raise ValueError(f"Expected a directory: {path}")

    known_dirs = ["gff", "genbank", "fasta", "report", "results"]
    summary: Dict[str, List[str]] = {}
    for dirname in known_dirs:
        subdir = path / dirname
        if subdir.exists() and subdir.is_dir():
            summary[dirname] = sorted(item.name for item in subdir.iterdir() if item.is_file())[:50]

    top_level = sorted(item.name for item in path.iterdir())[:50]
    content = f"Found result directory {path.name} with entries: {', '.join(top_level)}"
    return {"content": content, "data": {"path": str(path), "top_level": top_level, "known_outputs": summary}}


def run_annotation(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Run AnnotationPipeline synchronously into a session output directory."""
    from pathlib import Path as _Path
    from ..core.pipeline import AnnotationPipeline

    # Resolve input path: check session workspace first, then relative to workspace root
    input_arg = args["input"]
    fasta_path = _Path(input_arg)
    if not fasta_path.is_absolute():
        # Check in session workspace
        session_ws = _Path("./mitoflow_workspace") / context.session_id
        candidate = session_ws / input_arg
        if candidate.exists():
            fasta_path = candidate
        else:
            # Try workspace root
            fasta_path = ensure_under_root(input_arg, context.workspace_root)
    if not fasta_path.exists():
        raise FileNotFoundError(f"File not found: {fasta_path}. Upload it to the workspace first.")

    name = str(args.get("name") or fasta_path.stem)
    threads = int(args.get("threads") or 4)
    output_dir = context.output_root / "annotation" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline = AnnotationPipeline(threads=threads)
    result = pipeline.run(
        fasta_path=fasta_path,
        output_dir=output_dir,
        name=name,
        skip_trna=bool(args.get("skip_trna", False)),
        skip_rrna=bool(args.get("skip_rrna", False)),
        skip_qc=bool(args.get("skip_qc", False)),
        skip_mtpt=True,
    )
    return {
        "content": f"Annotation completed for {name}.",
        "data": {
            "output_dir": str(output_dir),
            "warnings": result.warnings,
        },
    }
