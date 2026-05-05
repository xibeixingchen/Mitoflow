"""Skills tools for AI agent workflow guidance and execution.

ClawBio pattern: skills are both documentation AND executable workflows.
The execute_skill tool maps skill names to MitoFlow module runners.
"""

from __future__ import annotations

from typing import Any, Dict

from .models import EntryPoint, SafetyLevel, ToolDefinition
from .skills import SkillRegistry
from .tools import ToolContext, ToolRegistry

_SKILLS: SkillRegistry | None = None

# Skill → MitoFlow module runner mapping
SKILL_EXECUTORS: Dict[str, str] = {
    "annotation": "mito_annotate",
    "qc": "mito_qc",
    "cms": "run_cms_analysis",
    "erc": "run_erc_analysis",
    "comparative": "run_comparative_analysis",
    "assembly": "mito_assemble",
}


def _get_skills() -> SkillRegistry:
    global _SKILLS
    if _SKILLS is None:
        _SKILLS = SkillRegistry()
    return _SKILLS


def register_skills_tools(registry: ToolRegistry) -> None:
    """Register skills tools — list, get, search, and execute."""
    registry.register(
        ToolDefinition(
            name="list_skills",
            description="List available workflow skills (assembly, annotation, QC, ERC, CMS, comparative).",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        list_skills,
    )
    registry.register(
        ToolDefinition(
            name="get_skill",
            description="Get detailed instructions for a specific workflow skill.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Skill name (assembly, annotation, quality_check, erc_analysis, cms_detection, comparative)."}
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        get_skill,
    )
    registry.register(
        ToolDefinition(
            name="find_skills_by_tag",
            description="Find skills related to a topic tag.",
            parameters={
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "Tag to search (e.g. 'assembly', 'cms', 'evolution')."}
                },
                "required": ["tag"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        find_skills_by_tag,
    )
    registry.register(
        ToolDefinition(
            name="execute_skill",
            description=(
                "Execute a workflow skill by routing to the appropriate MitoFlow module. "
                "Use AFTER get_skill to understand what the skill does. "
                "Supported skills: annotation (needs FASTA), qc (needs GenBank), "
                "cms (needs protein FASTAs), erc (needs paired organelle genomes), "
                "comparative (needs multi-species annotations)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "description": "Skill name to execute."},
                    "input": {"type": "string", "description": "Input file path (from workspace)."},
                    "name": {"type": "string", "description": "Project/sample name."},
                    "params": {"type": "object", "description": "Additional skill-specific parameters."},
                },
                "required": ["skill", "input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.LAUNCHES_JOB,
            entry_points=[EntryPoint.CLI, EntryPoint.API],
        ),
        execute_skill,
    )


def list_skills(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """List available skills."""
    skills = _get_skills()
    items = skills.list_skills()
    lines = [f"- **{s['name']}**: {s['description']} (tags: {', '.join(s['tags'])})" for s in items]
    return {
        "content": f"Available skills ({len(items)}):\n" + "\n".join(lines),
        "data": {"skills": items},
    }


def get_skill(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Get skill instructions."""
    skills = _get_skills()
    skill = skills.get(args["name"])
    if not skill:
        available = [s.name for s in skills._skills.values()]
        return {"content": f"Skill '{args['name']}' not found. Available: {', '.join(available)}", "data": {}}
    return {
        "content": skill.to_prompt(),
        "data": {"name": skill.name, "description": skill.description, "tags": skill.tags},
    }


def find_skills_by_tag(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Find skills by tag."""
    skills = _get_skills()
    found = skills.find_by_tag(args["tag"])
    if not found:
        return {"content": f"No skills found for tag '{args['tag']}'.", "data": {"skills": []}}
    lines = [f"- **{s.name}**: {s.description}" for s in found]
    return {
        "content": f"Skills matching '{args['tag']}':\n" + "\n".join(lines),
        "data": {"skills": [{"name": s.name, "description": s.description} for s in found]},
    }


def execute_skill(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Execute a skill by routing to the appropriate MitoFlow module runner."""
    skill_name = args["skill"].lower().strip()
    skills = _get_skills()
    skill = skills.get(skill_name)
    if not skill:
        available = [s.name for s in skills._skills.values()]
        return {"content": f"Unknown skill '{skill_name}'. Available: {', '.join(available)}", "data": {}}

    runner_name = SKILL_EXECUTORS.get(skill_name)
    if not runner_name:
        return {"content": f"Skill '{skill_name}' has no executable runner yet.", "data": {}}

    input_path = args["input"]
    project_name = args.get("name", Path(input_path).stem if input_path else skill_name)
    extra_params = args.get("params", {}) or {}

    # Route to the registered tool executor
    from .tools import ToolCall
    from .mitoflow_tools import mito_annotate, mito_visualize

    if runner_name == "mito_annotate":
        return mito_annotate({
            "input": input_path,
            "name": project_name,
            **extra_params,
        }, context)

    if runner_name == "mito_qc":
        return _run_qc_skill(input_path, project_name, context)

    if runner_name == "run_cms_analysis":
        return _run_cms_skill(input_path, project_name, context)

    return {
        "content": f"Skill '{skill_name}' → runner '{runner_name}' is registered but not yet wired. "
                   f"Use the CLI command directly: mitoflow {skill_name} -i {input_path}",
        "data": {"skill": skill_name, "runner": runner_name, "input": input_path},
    }


def _run_qc_skill(input_path: str, name: str, context: ToolContext) -> Dict[str, Any]:
    """Run QC assessment on an annotated GenBank file."""
    from pathlib import Path as _P
    gb_path = _P(input_path)
    if not gb_path.is_absolute():
        gb_path = context.workspace_root / context.session_id / input_path
    if not gb_path.exists():
        return {"content": f"GenBank file not found: {input_path}. Annotate first.", "data": {}}

    try:
        from ...qc.qc_engine import QCEngine
        engine = QCEngine(genome_path=gb_path)
        result = engine.run_all()
        return {
            "content": f"QC completed for {name}. Score: {result.quality_score:.1f}/100",
            "data": {"score": result.quality_score, "details": str(result)},
        }
    except Exception as e:
        return {"content": f"QC failed: {e}", "data": {}}


def _run_cms_skill(input_path: str, name: str, context: ToolContext) -> Dict[str, Any]:
    """Run CMS detection on protein sequences."""
    from pathlib import Path as _P
    prot_path = _P(input_path)
    if not prot_path.is_absolute():
        prot_path = context.workspace_root / context.session_id / input_path
    if not prot_path.exists():
        return {"content": f"Protein FASTA not found: {input_path}", "data": {}}

    try:
        from ...cms.predictor import CMSPredictor
        predictor = CMSPredictor()
        result = predictor.predict(prot_path)
        return {
            "content": f"CMS analysis completed for {name}. Found {len(result.matches)} potential CMS genes.",
            "data": {"matches": result.matches},
        }
    except Exception as e:
        return {"content": f"CMS analysis failed: {e}", "data": {}}
