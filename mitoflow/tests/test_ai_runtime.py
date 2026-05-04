"""Tests for the AI runtime manager loop."""

from mitoflow.ai.models import EntryPoint, SafetyLevel, ToolDefinition
from mitoflow.ai.providers import FakeProvider
from mitoflow.ai.runtime import AgentRuntime
from mitoflow.ai.sessions import LocalSessionStore
from mitoflow.ai.tools import ToolContext, ToolRegistry


def test_runtime_executes_tool_and_returns_final_answer(tmp_path):
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="list_modules",
            description="List MitoFlow modules",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI],
        ),
        lambda args, context: {
            "content": "Available modules: annotate, qc",
            "data": {"modules": ["annotate", "qc"]},
        },
    )
    store = LocalSessionStore(tmp_path / "sessions")
    session_id = store.create_session()
    provider = FakeProvider(
        responses=[
            {
                "content": "I will list modules.",
                "tool_calls": [
                    {"id": "call_1", "name": "list_modules", "arguments": {}},
                ],
            },
            {"content": "Available modules are annotate and qc."},
        ]
    )
    runtime = AgentRuntime(provider=provider, registry=registry, store=store, model="fake")
    context = ToolContext(
        session_id=session_id,
        workspace_root=tmp_path,
        output_root=tmp_path / "out",
        entry_point=EntryPoint.CLI,
    )

    result = runtime.run_turn(session_id=session_id, user_text="What can you do?", context=context)

    assert result.final_text == "Available modules are annotate and qc."
    assert result.tool_results[0].ok is True
    assert store.load_messages(session_id)[-1].role == "assistant"


def test_runtime_stops_after_max_turns(tmp_path):
    registry = ToolRegistry()
    store = LocalSessionStore(tmp_path / "sessions")
    session_id = store.create_session()
    provider = FakeProvider(
        responses=[
            {
                "content": "Unknown tool.",
                "tool_calls": [{"id": "call_1", "name": "missing", "arguments": {}}],
            },
            {
                "content": "Unknown tool again.",
                "tool_calls": [{"id": "call_2", "name": "missing", "arguments": {}}],
            },
        ]
    )
    runtime = AgentRuntime(
        provider=provider,
        registry=registry,
        store=store,
        model="fake",
        max_turns=1,
    )
    context = ToolContext(
        session_id=session_id,
        workspace_root=tmp_path,
        output_root=tmp_path / "out",
        entry_point=EntryPoint.CLI,
    )

    result = runtime.run_turn(session_id=session_id, user_text="Use a tool", context=context)

    assert "maximum tool turns" in result.final_text


def test_runtime_returns_direct_answer_without_tools(tmp_path):
    registry = ToolRegistry()
    store = LocalSessionStore(tmp_path / "sessions")
    session_id = store.create_session()
    provider = FakeProvider(responses=[{"content": "I can help with mitochondrial analysis."}])
    runtime = AgentRuntime(provider=provider, registry=registry, store=store, model="fake")
    context = ToolContext(
        session_id=session_id,
        workspace_root=tmp_path,
        output_root=tmp_path / "out",
        entry_point=EntryPoint.CLI,
    )

    result = runtime.run_turn(session_id=session_id, user_text="What can you do?", context=context)

    assert result.final_text == "I can help with mitochondrial analysis."
    assert result.tool_results == []
