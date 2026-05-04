"""Skills tools for AI agent workflow guidance."""

from __future__ import annotations

from typing import Any, Dict

from .models import EntryPoint, SafetyLevel, ToolDefinition
from .skills import SkillRegistry
from .tools import ToolContext, ToolRegistry

_SKILLS: SkillRegistry | None = None


def _get_skills() -> SkillRegistry:
    global _SKILLS
    if _SKILLS is None:
        _SKILLS = SkillRegistry()
    return _SKILLS


def register_skills_tools(registry: ToolRegistry) -> None:
    """Register skills tools."""
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
