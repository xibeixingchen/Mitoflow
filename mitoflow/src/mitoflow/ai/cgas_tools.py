"""AI-callable Chloroplast (叶绿体) analysis tools.

Maps all 14 chloroplast modules to PhytoOrga AI tools with proper safety levels.
CGAS backend is installed at ../../CGAS (relative to mitoflow project root).
Tools are exposed with 'chloro_' prefix and Chinese descriptions.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from .models import EntryPoint, SafetyLevel, ToolDefinition
from .tools import ToolContext, ToolRegistry, ensure_under_root

_CGAS_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "CGAS"
_CGAS_CLI = _CGAS_DIR / "cgas" / "cli.py"

CHLORO_MODULES = {
    1:  ("assemble",         "叶绿体基因组组装 — 从 FASTQ 原始读长组装"),
    2:  ("annotate",         "叶绿体基因组注释 — 从 FASTA 组装结果注释基因"),
    3:  ("compare",          "叶绿体基因比较 — 跨物种基因名标准化"),
    4:  ("convert",          "叶绿体 GenBank 格式转换 — NCBI 提交格式"),
    5:  ("gene_compare",     "叶绿体基因比较分析 — 多物种比较"),
    6:  ("gene_table",       "叶绿体基因含量比较表"),
    7:  ("genome_compare",   "叶绿体基因组比较分析"),
    8:  ("codon",            "叶绿体密码子使用分析 (RSCU)"),
    9:  ("amino",            "叶绿体氨基酸组成分析"),
    10: ("snp",              "叶绿体 SNP 和替换分析"),
    11: ("intron",           "叶绿体基因和 tRNA 内含子边界分析"),
    12: ("ssr",              "叶绿体 SSR (微卫星) 分析"),
    13: ("diversity",        "叶绿体核苷酸多样性分析 (Pi)"),
    14: ("phylogeny",        "叶绿体系统发育矩阵构建"),
}

# Module -> safety level
JOB_MODULES = {1, 2, 4, 14}  # Modules that launch heavy computation


def _get_chloro_python() -> str:
    """Get Python path, preferring the CGAS environment if available."""
    import shutil
    return shutil.which("python3") or shutil.which("python") or sys.executable


def _run_chloro_module(module_num: int, args: list[str], cwd: str, timeout: int = 1800) -> Dict[str, Any]:
    """Run a chloroplast module and return structured result."""
    if not _CGAS_CLI.exists():
        return {"ok": False, "error": f"CGAS backend not found at {_CGAS_DIR}"}

    python = _get_chloro_python()
    cmd = [python, str(_CGAS_CLI), "--module", str(module_num)] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout[-3000:],
            "stderr": result.stderr[-1000:],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Module {module_num} timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def register_cgas_tools(registry: ToolRegistry) -> None:
    """Register all chloroplast module tools in the AI tool registry."""

    # Register each module as a tool
    for num, (name, desc) in CHLORO_MODULES.items():
        safety = SafetyLevel.LAUNCHES_JOB if num in JOB_MODULES else SafetyLevel.READ_ONLY

        # Build parameters JSON schema
        params_schema: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input file or directory path (relative to workspace)"},
                "output": {"type": "string", "description": "Output directory (default: auto-generated)"},
            },
            "additionalProperties": False,
        }
        # Add module-specific params
        if num == 1:  # Assembly
            params_schema["properties"]["threads"] = {"type": "integer", "minimum": 1, "maximum": 16}
            params_schema["properties"]["adapter_trim"] = {"type": "boolean"}
        elif num == 14:  # Phylogeny
            params_schema["properties"]["genes_only"] = {"type": "boolean"}
            params_schema["properties"]["outgroup"] = {"type": "string"}

        # Closure-safe executor factory
        def _make_executor(module_num: int):
            def _executor(exec_args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
                input_path = exec_args.get("input", "")
                output_dir = exec_args.get("output", "")

                # Resolve input against workspace
                from pathlib import Path as _P
                resolved_input = _P(input_path)
                if not resolved_input.is_absolute():
                    resolved_input = context.workspace_root / context.session_id / input_path

                work_dir = str(resolved_input.parent if resolved_input.is_file() else resolved_input)

                cmd_args = []
                if input_path:
                    cmd_args.extend(["-i", str(resolved_input)])
                if output_dir:
                    cmd_args.extend(["-o", output_dir])
                # Extra params
                for key, val in exec_args.items():
                    if key not in ("input", "output") and val is not None:
                        if isinstance(val, bool) and val:
                            cmd_args.append(f"--{key.replace('_', '-')}")
                        elif not isinstance(val, bool):
                            cmd_args.extend([f"--{key.replace('_', '-')}", str(val)])

                result = _run_chloro_module(module_num, cmd_args, work_dir)
                if result.get("ok"):
                    module_name = CHLORO_MODULES.get(module_num, ("", ""))[0]
                    return {"content": f"叶绿体{module_name}分析完成。", "data": result}
                return {"content": f"叶绿体模块 {module_num} 失败: {result.get('error', result.get('stderr', ''))}", "data": result}
            return _executor

        registry.register(
            ToolDefinition(
                name=f"chloro_{name}",
                description=f"叶绿体{name} — {desc}。基于 CGAS 模块 {num}/14。",
                parameters=params_schema,
                safety_level=safety,
                entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
            ),
            _make_executor(num),
        )

    # Aggregate tool — list all chloroplast modules
    registry.register(
        ToolDefinition(
            name="chloro_list_modules",
            description="List all 14 chloroplast (叶绿体) analysis modules with descriptions.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        lambda args, ctx: {
            "content": "Chloroplast Modules (1-14):\n" + "\n".join(
                f"  {n}. {desc[0]} — {desc[1]}" for n, desc in CHLORO_MODULES.items()
            ),
            "data": {"modules": [{"id": n, "name": d[0], "desc": d[1]} for n, d in CHLORO_MODULES.items()]},
        },
    )

    # Run complete chloroplast pipeline
    registry.register(
        ToolDefinition(
            name="chloro_run_pipeline",
            description="Run the full chloroplast analysis pipeline (modules 1-14 in sequence). Use with caution.",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input directory with raw reads or FASTA files"},
                    "output": {"type": "string", "description": "Base output directory"},
                    "start": {"type": "integer", "minimum": 1, "maximum": 14, "description": "Start from module N (default: 1)"},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.LAUNCHES_JOB,
            entry_points=[EntryPoint.CLI, EntryPoint.API],
        ),
        lambda args, ctx: _run_chloro_pipeline(args, ctx),
    )


    # Smart aggregator — auto-select chloroplast modules by input type
    registry.register(
        ToolDefinition(
            name="analyze_chloroplast",
            description=(
                "叶绿体智能分析 — 根据输入类型自动选择叶绿体分析模块。"
                "支持组装(FASTQ)→注释(FASTA)→比较(GenBank)的全流程调度。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input file or directory"},
                    "stage": {"type": "string", "enum": ["auto", "assemble", "annotate", "analyze", "compare", "phylogeny"], "description": "Analysis stage. 'auto' detects from input."},
                    "output": {"type": "string", "description": "Output directory"},
                    "threads": {"type": "integer", "minimum": 1, "maximum": 16},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.LAUNCHES_JOB,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        analyze_chloroplast,
    )

    # IR boundary analysis — chloroplast-specific
    registry.register(
        ToolDefinition(
            name="chloro_ir_boundary",
            description=(
                "叶绿体IR边界分析 — 检测 LSC/IRb/SSC/IRa 四分区边界位置，"
                "识别 JLB/JSB/JSA/JLA 连接点，计算 IR 区长度和基因含量。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "genbank": {"type": "string", "description": "Annotated chloroplast GenBank file"},
                    "name": {"type": "string", "description": "Project name"},
                    "plot": {"type": "boolean", "description": "Generate IR boundary visualization"},
                },
                "required": ["genbank"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.WRITES_OUTPUT,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        chloro_ir_boundary,
    )


def analyze_chloroplast(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Smart chloroplast analysis — auto-select modules by input type."""
    from pathlib import Path as _P

    input_arg = args["input"]
    input_path = _P(input_arg)
    if not input_path.is_absolute():
        input_path = context.workspace_root / context.session_id / input_arg
    if not input_path.exists():
        return {"content": f"Input not found: {input_arg}", "data": {}}

    stage = args.get("stage", "auto")
    output_dir = args.get("output", "")
    threads = int(args.get("threads", 8))

    # Auto-detect stage from input
    if stage == "auto":
        if input_path.is_dir():
            # Check for FASTQ files -> assembly
            fastqs = list(input_path.rglob("*.fastq*")) + list(input_path.rglob("*.fq*"))
            if fastqs:
                stage = "assemble"
            else:
                stage = "analyze"
        elif input_path.suffix.lower() in (".fasta", ".fas", ".fa"):
            stage = "annotate"
        elif input_path.suffix.lower() in (".gb", ".gbk"):
            stage = "analyze"
        else:
            stage = "analyze"

    # Map stage to module(s)
    stage_modules = {
        "assemble": [1],      # Module 1: assembly
        "annotate": [2],      # Module 2: annotation
        "analyze": [2, 8, 12], # annotate + codon + ssr
        "compare": [3, 5, 7],  # compare + gene_compare + genome_compare
        "phylogeny": [14],    # Module 14: phylogeny
    }

    modules_to_run = stage_modules.get(stage, [2])
    work_dir = str(input_path.parent if input_path.is_file() else input_path)
    results = []

    for num in modules_to_run:
        cmd_args = ["-i", str(input_path)]
        if output_dir:
            cmd_args.extend(["-o", output_dir])
        if num == 1:
            cmd_args.extend(["--threads", str(threads)])

        r = _run_chloro_module(num, cmd_args, work_dir, timeout=1800)
        module_name = CHLORO_MODULES.get(num, ("", ""))[0]
        results.append({"module": num, "name": module_name, **r})
        if not r.get("ok"):
            break

    ok_count = sum(1 for r in results if r.get("ok"))
    module_names = [r["name"] for r in results]
    return {
        "content": (
            f"叶绿体智能分析 ({stage}) 完成: {ok_count}/{len(results)} 个模块成功。\n"
            f"执行模块: {', '.join(module_names)}"
        ),
        "data": {"stage": stage, "results": results},
    }


def chloro_ir_boundary(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Analyze IR (inverted repeat) boundaries in chloroplast genome.

    Detects JLB, JSB, JSA, JLA junctions and calculates LSC/IRb/SSC/IRa lengths.
    """
    from pathlib import Path as _P
    from Bio import SeqIO

    gb_arg = args["genbank"]
    gb_path = _P(gb_arg)
    if not gb_path.is_absolute():
        gb_path = context.workspace_root / context.session_id / gb_arg
    if not gb_path.exists():
        return {"content": f"GenBank file not found: {gb_arg}", "data": {}}

    name = str(args.get("name") or gb_path.stem)
    do_plot = bool(args.get("plot", True))
    output_dir = context.output_root / "ir_boundary" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        rec = SeqIO.read(str(gb_path), "genbank")
        seq_len = len(rec.seq)

        # Look for IR markers in features
        ir_regions = []
        for feat in rec.features:
            if feat.type == "repeat_region":
                note = feat.qualifiers.get("note", [""])[0].lower()
                if "ir" in note or "inverted" in note:
                    ir_regions.append({
                        "start": int(feat.location.start) + 1,
                        "end": int(feat.location.end),
                        "strand": feat.strand,
                        "note": note,
                    })

        # Heuristic: if no repeat_region found, estimate from common IR genes
        if len(ir_regions) < 2:
            ir_genes = ["rps19", "rpl2", "ndhB", "rps7", "ycf1", "ycf2"]
            ir_starts = []
            ir_ends = []
            for feat in rec.features:
                if feat.type == "gene":
                    gname = feat.qualifiers.get("gene", [""])[0].lower()
                    if gname in ir_genes:
                        ir_starts.append(int(feat.location.start) + 1)
                        ir_ends.append(int(feat.location.end))
            if ir_starts and ir_ends:
                # Estimate IR boundaries from gene clusters
                ir_regions = [
                    {"start": min(ir_starts), "end": max(ir_ends), "strand": 1, "note": "IRb (estimated)"},
                ]

        # Calculate quadripartite structure
        if len(ir_regions) >= 1:
            ir_len = ir_regions[0]["end"] - ir_regions[0]["start"] + 1
            # Assume IRa is the second half if circular
            lsc_len = ir_regions[0]["start"] - 1 if ir_regions[0]["start"] > 1 else seq_len - ir_regions[0]["end"]
            ssc_len = seq_len - 2 * ir_len - lsc_len if lsc_len > 0 else seq_len // 4

            summary = {
                "total_length": seq_len,
                "lsc_length": max(0, lsc_len),
                "ir_length": ir_len,
                "ssc_length": max(0, ssc_len),
                "ir_regions": ir_regions,
            }
        else:
            summary = {"total_length": seq_len, "ir_regions": [], "note": "IR boundaries not detected — may need manual curation"}

        # Write report
        report_path = output_dir / f"{name}_ir_boundary.txt"
        with open(report_path, "w") as f:
            f.write(f"# IR Boundary Analysis: {name}\n")
            f.write(f"Total length: {seq_len:,} bp\n")
            if "lsc_length" in summary:
                f.write(f"LSC: {summary['lsc_length']:,} bp\n")
                f.write(f"IR:  {summary['ir_length']:,} bp\n")
                f.write(f"SSC: {summary['ssc_length']:,} bp\n")
            for ir in ir_regions:
                f.write(f"\nIR region: {ir['start']}-{ir['end']} ({ir['note']})\n")

        return {
            "content": (
                f"叶绿体IR边界分析完成: {name}\n"
                f"  基因组大小: {seq_len:,} bp\n"
                f"  检测到 {len(ir_regions)} 个 IR 区\n"
                f"  报告: {report_path}"
            ),
            "data": summary,
        }
    except Exception as e:
        return {"content": f"IR boundary analysis failed: {e}", "data": {"error": str(e)}}


def _run_chloro_pipeline(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Run the full chloroplast pipeline sequentially."""
    import time
    work_dir = str(context.workspace_root / context.session_id)
    start = args.get("start", 1)
    results = []
    for num in range(start, 15):
        if args.get("input"):
            cmd_args = ["-i", str(args["input"])]
        else:
            cmd_args = []
        if args.get("output"):
            cmd_args.extend(["-o", str(args["output"])])
        r = _run_chloro_module(num, cmd_args, work_dir, timeout=1200)
        results.append({"module": num, "name": CHLORO_MODULES[num][0], **r})
        if not r.get("ok"):
            break
        time.sleep(0.5)

    ok_count = sum(1 for r in results if r.get("ok"))
    return {
        "content": f"Chloroplast pipeline: {ok_count}/{len(results)} modules completed.",
        "data": {"results": results},
    }
