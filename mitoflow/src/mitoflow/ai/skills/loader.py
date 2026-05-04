"""ClawBio-style SKILL.md loader — loads skill specs as structured data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

_SKILLS_DIR = Path(__file__).parent


class SkillSpec:
    """A loaded SKILL.md specification."""

    def __init__(self, name: str, path: Path, content: str) -> None:
        self.name = name
        self.path = path
        self.content = content
        self._parse(content)

    def _parse(self, content: str) -> None:
        lines = content.strip().split("\n")
        self.title = ""
        self.contract = ""
        self.workflow: List[str] = []
        self.tools: List[Dict[str, str]] = []
        self.parameters: List[Dict[str, str]] = []
        self.references: List[str] = []

        section = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                self.title = stripped.lstrip("# ").strip()
            elif stripped == "## Contract":
                section = "contract"
            elif stripped == "## Workflow":
                section = "workflow"
            elif stripped == "## Tools":
                section = "tools"
            elif stripped == "## Parameters":
                section = "params"
            elif stripped == "## References":
                section = "refs"
            elif section == "contract" and stripped and not stripped.startswith("#"):
                self.contract = stripped
            elif section == "workflow" and stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.")):
                self.workflow.append(stripped)
            elif section == "refs" and stripped.startswith("- "):
                self.references.append(stripped.lstrip("- "))

    def to_prompt_context(self) -> str:
        """Format as a compact LLM context block."""
        lines = [f"## Skill: {self.title}"]
        if self.contract:
            lines.append(f"Contract: {self.contract}")
        if self.workflow:
            lines.append("Workflow:")
            lines.extend(f"  {step}" for step in self.workflow)
        if self.references:
            lines.append("References:")
            lines.extend(f"  - {ref}" for ref in self.references)
        return "\n".join(lines)


class SkillLoader:
    """Load ClawBio-style SKILL.md specifications."""

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        self._skills_dir = skills_dir or _SKILLS_DIR
        self._skills: Optional[Dict[str, SkillSpec]] = None

    @property
    def skills(self) -> Dict[str, SkillSpec]:
        if self._skills is None:
            self._skills = self._load()
        return self._skills

    def _load(self) -> Dict[str, SkillSpec]:
        skills: Dict[str, SkillSpec] = {}
        for skill_dir in self._skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
                spec = SkillSpec(skill_dir.name, skill_md, content)
                skills[skill_dir.name] = spec
            except Exception:
                continue
        return skills

    def get(self, name: str) -> Optional[SkillSpec]:
        return self.skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        return [
            {"name": s.name, "title": s.title, "contract": s.contract[:100]}
            for s in self.skills.values()
        ]

    def context_for_skill(self, name: str) -> Optional[str]:
        spec = self.get(name)
        return spec.to_prompt_context() if spec else None

    def all_context(self) -> str:
        """All skill contexts combined for system prompt augmentation."""
        return "\n\n".join(s.to_prompt_context() for s in self.skills.values())
