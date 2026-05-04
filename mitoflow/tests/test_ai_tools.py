"""Tests for AI tool registry and safety helpers."""

from pathlib import Path

import pytest

from mitoflow.ai.models import EntryPoint, SafetyLevel, ToolCall, ToolDefinition
from mitoflow.ai.tools import ToolContext, ToolRegistry, ensure_under_root


def test_registry_rejects_duplicate_tool_names():
    registry = ToolRegistry()
    definition = ToolDefinition(
        name="echo",
        description="Echo input",
        parameters={"type": "object", "properties": {}},
        safety_level=SafetyLevel.READ_ONLY,
        entry_points=[EntryPoint.CLI],
    )

    registry.register(definition, lambda args, context: {"ok": True, "args": args})

    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition, lambda args, context: {"ok": True})


def test_registry_executes_registered_tool(tmp_path):
    registry = ToolRegistry()
    definition = ToolDefinition(
        name="echo",
        description="Echo input",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        safety_level=SafetyLevel.READ_ONLY,
        entry_points=[EntryPoint.CLI],
    )
    registry.register(definition, lambda args, context: {"text": args["text"]})
    context = ToolContext(
        session_id="s1",
        workspace_root=tmp_path,
        output_root=tmp_path / "out",
        entry_point=EntryPoint.CLI,
    )

    result = registry.execute(
        ToolCall(id="call_1", name="echo", arguments={"text": "hello"}),
        context,
    )

    assert result.ok is True
    assert result.data == {"text": "hello"}


def test_registry_blocks_entry_point_not_allowed(tmp_path):
    registry = ToolRegistry()
    definition = ToolDefinition(
        name="api_only",
        description="API only",
        parameters={"type": "object", "properties": {}},
        safety_level=SafetyLevel.READ_ONLY,
        entry_points=[EntryPoint.API],
    )
    registry.register(definition, lambda args, context: {"ok": True})
    context = ToolContext(
        session_id="s1",
        workspace_root=tmp_path,
        output_root=tmp_path / "out",
        entry_point=EntryPoint.CLI,
    )

    result = registry.execute(ToolCall(id="call_1", name="api_only", arguments={}), context)

    assert result.ok is False
    assert "not available" in result.content


def test_ensure_under_root_accepts_child_path(tmp_path):
    child = tmp_path / "sample.fasta"
    child.write_text(">x\nATGC\n")

    resolved = ensure_under_root(child, tmp_path)

    assert resolved == child.resolve()


def test_ensure_under_root_rejects_parent_escape(tmp_path):
    outside = Path("/tmp/outside.fasta")

    with pytest.raises(ValueError, match="outside allowed root"):
        ensure_under_root(outside, tmp_path)


def test_registry_handles_unregistered_tool(tmp_path):
    registry = ToolRegistry()
    context = ToolContext(
        session_id="s1",
        workspace_root=tmp_path,
        output_root=tmp_path / "out",
        entry_point=EntryPoint.CLI,
    )

    result = registry.execute(ToolCall(id="call_1", name="missing", arguments={}), context)

    assert result.ok is False
    assert "not registered" in result.content


def test_registry_handles_executor_exception(tmp_path):
    registry = ToolRegistry()

    def failing_executor(args, context):
        raise RuntimeError("boom")

    registry.register(
        ToolDefinition(
            name="fail",
            description="Always fails",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI],
        ),
        failing_executor,
    )
    context = ToolContext(
        session_id="s1",
        workspace_root=tmp_path,
        output_root=tmp_path / "out",
        entry_point=EntryPoint.CLI,
    )

    result = registry.execute(ToolCall(id="call_1", name="fail", arguments={}), context)

    assert result.ok is False
    assert "boom" in result.content


def test_registry_list_definitions_filtered(tmp_path):
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="cli_tool",
            description="CLI",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI],
        ),
        lambda args, ctx: {},
    )
    registry.register(
        ToolDefinition(
            name="api_tool",
            description="API",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.API],
        ),
        lambda args, ctx: {},
    )

    cli_tools = registry.definitions(EntryPoint.CLI)
    api_tools = registry.definitions(EntryPoint.API)
    all_tools = registry.definitions()

    assert len(cli_tools) == 1
    assert cli_tools[0].name == "cli_tool"
    assert len(api_tools) == 1
    assert api_tools[0].name == "api_tool"
    assert len(all_tools) == 2
