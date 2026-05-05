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

    from .cgas_tools import register_cgas_tools
    register_cgas_tools(registry)

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
            name="mito_annotate",
            description="线粒体注释 — 对 FASTA 文件进行 PCG/tRNA/rRNA 基因注释。基于 MitoFlow 注释流水线。",
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
        mito_annotate,
    )

    # ── Wave 1: 线粒体模块补全 ──────────────────────────────────────
    registry.register(
        ToolDefinition(
            name="mito_assemble",
            description=(
                "线粒体组装 — 植物线粒体基因组组装。基于 Ni et al. (2025) PBJ 综述文献，"
                "支持长读长 (PacBio HiFi / ONT) 和混合策略。自动检测并调用 Oatk / GetOrganelle / Flye。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input reads directory or FASTA file."},
                    "strategy": {"type": "string", "enum": ["hifi_only", "ont_only", "hybrid", "short_read"], "description": "Assembly strategy per Ni2025: hifi_only (PacBio HiFi), ont_only (ONT long-read), hybrid (long+short), short_read (Illumina only)"},
                    "tool": {"type": "string", "enum": ["auto", "oatk", "getorganelle", "flye", "nextdenovo"], "description": "Assembler. 'auto' selects per strategy (oatk for hifi, flye for ont, getorganelle for hybrid/short)"},
                    "threads": {"type": "integer", "minimum": 1, "maximum": 64},
                    "name": {"type": "string", "description": "Project name."},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.LAUNCHES_JOB,
            entry_points=[EntryPoint.CLI, EntryPoint.API],
        ),
        mito_assemble,
    )

    registry.register(
        ToolDefinition(
            name="mito_qc",
            description="线粒体质控 — 五维质量评估：完整性、连续性、正确性、污染、结构。输出评分和可视化报告。",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Path to mitochondrial genome FASTA."},
                    "name": {"type": "string", "description": "Project name."},
                    "cp": {"type": "string", "description": "Optional chloroplast FASTA for MTPT contamination check."},
                    "bam": {"type": "string", "description": "Optional BAM file for coverage analysis."},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.WRITES_OUTPUT,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        mito_qc,
    )

    registry.register(
        ToolDefinition(
            name="mito_codon",
            description="线粒体密码子分析 — RSCU 相对同义密码子使用度分析。基于 MitoFlow codon 模块。",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Path to GenBank or FASTA file."},
                    "name": {"type": "string", "description": "Project name."},
                    "plot": {"type": "boolean", "description": "Generate RSCU plots."},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        mito_codon,
    )

    registry.register(
        ToolDefinition(
            name="mito_gc",
            description="线粒体GC分析 — GC含量、GC skew分析，支持窗口滑动统计和可视化。",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Path to GenBank or FASTA file."},
                    "name": {"type": "string", "description": "Project name."},
                    "window": {"type": "integer", "description": "Sliding window size (default: 200)."},
                    "plot": {"type": "boolean", "description": "Generate GC profile plot."},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.WRITES_OUTPUT,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        mito_gc,
    )

    registry.register(
        ToolDefinition(
            name="mito_phylogeny",
            description="线粒体系统发育 — 多物种蛋白编码基因比对、串联矩阵构建，输出用于 IQ-TREE 的输入。",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Directory with GenBank files or glob pattern."},
                    "name": {"type": "string", "description": "Project name."},
                    "genes": {"type": "string", "description": "Comma-separated gene list (default: cox1,cob,nad5,atp6,atp1)"},
                    "outgroup": {"type": "string", "description": "Outgroup species name."},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.LAUNCHES_JOB,
            entry_points=[EntryPoint.CLI, EntryPoint.API],
        ),
        mito_phylogeny,
    )

    registry.register(
        ToolDefinition(
            name="mito_visualize",
            description=(
                "线粒体可视化 — 生成线粒体基因组图谱。支持环形图 (pycirclize)、线性图 (pygenomeviz)、"
                "OGDraw 质量图 (gbdraw)、GC 含量图。输入为注释后的 GenBank 文件。"
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
        mito_visualize,
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

    # Use the session-specific workspace directory from context
    ws = context.workspace_root / context.session_id

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


def mito_visualize(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Generate visualization plots for a mitochondrial genome."""
    from pathlib import Path as _Path
    input_arg = args["genbank_file"]
    gb_path = _Path(input_arg)
    if not gb_path.is_absolute():
        session_ws = context.workspace_root / context.session_id
        candidate = session_ws / input_arg
        if candidate.exists():
            gb_path = candidate
        else:
            # Check annotation artifacts in session output
            art_ws = context.output_root
            for cand in art_ws.rglob(input_arg):
                gb_path = cand; break
    if not gb_path.exists():
        return {"content": f"GenBank file not found: {input_arg}", "data": {}}

    viz_type = args.get("viz_type", "circular")
    output_dir = context.workspace_root / context.session_id / "viz"
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


def mito_annotate(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Run AnnotationPipeline synchronously into a session output directory."""
    from pathlib import Path as _Path
    from ..core.pipeline import AnnotationPipeline

    # Resolve input path: check session workspace first, then relative to workspace root
    input_arg = args["input"]
    fasta_path = _Path(input_arg)
    if not fasta_path.is_absolute():
        # Check in session workspace
        session_ws = context.workspace_root / context.session_id
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
        "content": f"线粒体注释完成: {name}。",
        "data": {
            "output_dir": str(output_dir),
            "warnings": result.warnings,
        },
    }


def _resolve_input_path(input_arg: str, context: ToolContext) -> Path:
    """Resolve input path against session workspace."""
    from pathlib import Path as _Path
    p = _Path(input_arg)
    if not p.is_absolute():
        session_ws = context.workspace_root / context.session_id
        candidate = session_ws / input_arg
        if candidate.exists():
            p = candidate
        else:
            p = ensure_under_root(input_arg, context.workspace_root)
    return p


def mito_assemble(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Mitochondrial genome assembly based on Ni et al. (2025) PBJ review.

    Strategy selection per literature:
      - hifi_only:  PacBio HiFi → Oatk (best contiguity)
      - ont_only:   ONT long-read → Flye or NextDenovo
      - hybrid:     Long + Illumina → GetOrganelle (best correctness)
      - short_read: Illumina only → GetOrganelle
    """
    from pathlib import Path as _Path
    import shutil

    input_arg = args["input"]
    input_path = _resolve_input_path(input_arg, context)
    if not input_path.exists():
        return {"content": f"Input not found: {input_arg}", "data": {}}

    strategy = args.get("strategy", "hifi_only")
    tool = args.get("tool", "auto")
    threads = int(args.get("threads") or 8)
    name = str(args.get("name") or input_path.stem)
    output_dir = context.output_root / "assembly" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Auto-select tool per strategy (Ni et al. 2025 recommendations)
    if tool == "auto":
        tool = {
            "hifi_only": "oatk",
            "ont_only": "flye",
            "hybrid": "getorganelle",
            "short_read": "getorganelle",
        }.get(strategy, "oatk")

    # Check tool availability
    tool_exe = shutil.which(tool) if tool != "getorganelle" else shutil.which("get_organelle_from_reads.py")
    if not tool_exe and tool != "nextdenovo":
        return {
            "content": f"Assembler '{tool}' not found in PATH. Install it first.",
            "data": {"strategy": strategy, "tool": tool, "literature_ref": "Ni2025_PBJ"},
        }

    # Build command based on tool
    cmd = []
    if tool == "oatk":
        # Oatk: k-mer based organelle assembly from HiFi reads
        cmd = [tool_exe, "-t", str(threads), "-o", str(output_dir), str(input_path)]
    elif tool == "flye":
        # Flye: de novo assembly for ONT
        cmd = [tool_exe, "--meta", "--threads", str(threads), "--out-dir", str(output_dir), "--pacbio-hifi" if strategy == "hifi_only" else "--nano-raw", str(input_path)]
    elif tool == "getorganelle":
        # GetOrganelle: organelle-specific assembly
        cmd = [tool_exe, "-t", str(threads), "-o", str(output_dir), "-1", str(input_path)]
    elif tool == "nextdenovo":
        # NextDenovo: ONT assembly (needs config file)
        return {
            "content": f"NextDenovo requires a config file. Please prepare run.cfg manually.",
            "data": {"strategy": strategy, "tool": tool},
        }

    # Run assembly
    try:
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        ok = result.returncode == 0
        return {
            "content": f"线粒体组装{'完成' if ok else '失败'} ({tool}, {strategy}).\n" + result.stdout[-1000:],
            "data": {
                "ok": ok,
                "tool": tool,
                "strategy": strategy,
                "output_dir": str(output_dir),
                "literature_ref": "Ni2025_PBJ",
                "stderr": result.stderr[-500:] if not ok else "",
            },
        }
    except Exception as e:
        return {"content": f"Assembly failed: {e}", "data": {"error": str(e)}}


def mito_qc(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Run five-dimensional QC on a mitochondrial genome."""
    from pathlib import Path as _Path
    from ..core.input import load_fasta
    from ..qc.qc_engine import QCEngine
    from ..db.manager import DBManager

    input_arg = args["input"]
    fasta_path = _resolve_input_path(input_arg, context)
    if not fasta_path.exists():
        return {"content": f"FASTA not found: {input_arg}", "data": {}}

    name = str(args.get("name") or fasta_path.stem)
    output_dir = context.output_root / "qc" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Optional files
    cp_path = args.get("cp")
    bam_path = args.get("bam")
    cp_fasta = _resolve_input_path(cp_path, context) if cp_path else None
    bam_file = _resolve_input_path(bam_path, context) if bam_path else None

    try:
        genome = load_fasta(fasta_path)
        db_mgr = DBManager()
        engine = QCEngine(db_manager=db_mgr)
        result = engine.run(
            genome=genome,
            fasta_path=fasta_path,
            cp_fasta=cp_fasta,
            bam_path=bam_file,
            output_dir=output_dir,
            name=name,
        )
        return {
            "content": f"线粒体质控完成: {name}\n{result.summary()}",
            "data": {
                "score": result.score.quality_score if result.score else None,
                "passed": result.passed,
                "output_dir": str(output_dir),
            },
        }
    except Exception as e:
        return {"content": f"QC failed: {e}", "data": {"error": str(e)}}


def mito_codon(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Codon usage analysis (RSCU) for mitochondrial genes."""
    from pathlib import Path as _Path

    input_arg = args["input"]
    input_path = _resolve_input_path(input_arg, context)
    if not input_path.exists():
        return {"content": f"File not found: {input_arg}", "data": {}}

    name = str(args.get("name") or input_path.stem)
    do_plot = bool(args.get("plot", True))
    output_dir = context.output_root / "codon" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from ..codon.analysis import analyze_codon_usage
        from ..codon.visualize import plot_rscu_heatmap

        result = analyze_codon_usage(input_path)

        plot_files = []
        if do_plot and result.overall_rscu:
            plot_path = output_dir / f"{name}_rscu.png"
            plot_rscu_heatmap(result.per_gene_rscu, str(plot_path), title=f"{name} RSCU Heatmap")
            plot_files.append(str(plot_path))

        return {
            "content": f"线粒体密码子分析完成: {name}。\n{result.summary()}",
            "data": {
                "genes": result.n_genes,
                "codons": result.total_codons,
                "mean_enc": result.mean_enc,
                "plots": plot_files,
                "output_dir": str(output_dir),
            },
        }
    except Exception as e:
        return {"content": f"Codon analysis failed: {e}", "data": {"error": str(e)}}


def mito_gc(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """GC content and GC skew analysis for mitochondrial genome."""
    from pathlib import Path as _Path

    input_arg = args["input"]
    input_path = _resolve_input_path(input_arg, context)
    if not input_path.exists():
        return {"content": f"File not found: {input_arg}", "data": {}}

    name = str(args.get("name") or input_path.stem)
    window = int(args.get("window", 200))
    do_plot = bool(args.get("plot", True))
    output_dir = context.output_root / "gc" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from ..viz.gc_content import plot_gc_profile
        from Bio import SeqIO

        rec = SeqIO.read(str(input_path), "genbank" if input_path.suffix in (".gb", ".gbk") else "fasta")
        seq = str(rec.seq)
        gc_total = (seq.count("G") + seq.count("C")) / len(seq) * 100

        plot_files = []
        if do_plot:
            plot_path = output_dir / f"{name}_gc.png"
            plot_gc_profile(seq, window=window, output_path=str(plot_path), title=f"{name} GC Profile")
            plot_files.append(str(plot_path))

        return {
            "content": f"线粒体GC分析完成: {name}。GC含量={gc_total:.1f}%, 窗口={window}bp。",
            "data": {
                "gc_content": round(gc_total, 2),
                "length": len(seq),
                "window": window,
                "plots": plot_files,
                "output_dir": str(output_dir),
            },
        }
    except Exception as e:
        return {"content": f"GC analysis failed: {e}", "data": {"error": str(e)}}


def mito_phylogeny(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Build phylogenetic matrix from mitochondrial protein-coding genes."""
    from pathlib import Path as _Path
    import glob

    input_arg = args["input"]
    input_path = _resolve_input_path(input_arg, context)
    if not input_path.exists():
        return {"content": f"Input not found: {input_arg}", "data": {}}

    name = str(args.get("name") or "phylo")
    gene_list = [g.strip() for g in args.get("genes", "cox1,cob,nad5,atp6,atp1").split(",")]
    outgroup = args.get("outgroup", "")
    output_dir = context.output_root / "phylogeny" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect GenBank files
    gb_files = []
    if input_path.is_dir():
        gb_files = sorted(input_path.glob("*.gb")) + sorted(input_path.glob("*.gbk"))
    else:
        gb_files = [input_path]

    if not gb_files:
        return {"content": "No GenBank files found.", "data": {}}

    try:
        from ..phylo.alignment import align_and_concatenate

        result = align_and_concatenate(
            genbank_files=[str(f) for f in gb_files],
            output_dir=output_dir,
            sequence_type="protein",
            min_presence=0.8,
        )

        lines = [
            f"线粒体系统发育矩阵构建完成: {name}",
            f"  物种数: {len(gb_files)}",
            f"  共享基因: {len(result.shared_genes)}",
            f"  输出: {result.output_files}",
        ]
        if outgroup:
            lines.append(f"  外群: {outgroup}")
        lines.append("下一步: 使用 IQ-TREE 构建系统发育树")

        return {
            "content": "\n".join(lines),
            "data": {
                "species": len(gb_files),
                "genes": result.shared_genes,
                "output_files": result.output_files,
                "output_dir": str(output_dir),
            },
        }
    except Exception as e:
        return {"content": f"Phylogeny matrix build failed: {e}", "data": {"error": str(e)}}
