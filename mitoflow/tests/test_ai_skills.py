"""Tests for skills registry and tools."""

from __future__ import annotations

import pytest

from mitoflow.ai.skills import Skill, SkillRegistry


@pytest.fixture()
def skills() -> SkillRegistry:
    return SkillRegistry()


class TestSkillRegistry:
    def test_builtin_skills_loaded(self, skills: SkillRegistry) -> None:
        all_skills = skills.list_skills()
        assert len(all_skills) >= 5
        names = [s["name"] for s in all_skills]
        assert "assembly" in names
        assert "annotation" in names
        assert "cms_detection" in names

    def test_get_skill(self, skills: SkillRegistry) -> None:
        skill = skills.get("assembly")
        assert skill is not None
        assert skill.name == "assembly"
        assert "GetOrganelle" in skill.instructions

    def test_get_missing_skill(self, skills: SkillRegistry) -> None:
        skill = skills.get("nonexistent")
        assert skill is None

    def test_find_by_tag(self, skills: SkillRegistry) -> None:
        found = skills.find_by_tag("cms")
        assert len(found) > 0
        assert any(s.name == "cms_detection" for s in found)

    def test_find_by_tag_empty(self, skills: SkillRegistry) -> None:
        found = skills.find_by_tag("nonexistent_tag")
        assert found == []

    def test_skill_to_prompt(self, skills: SkillRegistry) -> None:
        skill = skills.get("annotation")
        assert skill is not None
        prompt = skill.to_prompt()
        assert "## Skill: annotation" in prompt
        assert "mitofleshoot annotate" in prompt

    def test_register_custom_skill(self, skills: SkillRegistry) -> None:
        custom = Skill(
            name="test_skill",
            description="Test skill",
            instructions="Do something",
            tags=["test"],
        )
        skills.register(custom)
        assert skills.get("test_skill") is not None

    def test_all_skills_have_instructions(self, skills: SkillRegistry) -> None:
        for skill_data in skills.list_skills():
            skill = skills.get(skill_data["name"])
            assert skill is not None
            assert len(skill.instructions) > 100
