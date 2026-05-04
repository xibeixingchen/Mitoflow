"""Tests for AI service and default MitoFlow tools."""

from mitoflow.ai.models import EntryPoint
from mitoflow.ai.providers import FakeProvider
from mitoflow.ai.service import AIService, build_default_registry


def test_default_registry_has_core_tools():
    registry = build_default_registry()
    names = {tool.name for tool in registry.definitions(EntryPoint.CLI)}

    assert "list_mitoflow_modules" in names
    assert "summarize_result_directory" in names
    assert "run_annotation" in names


def test_service_creates_session_and_sends_message(tmp_path):
    registry = build_default_registry()
    provider = FakeProvider(
        responses=[
            {
                "content": "I will list modules.",
                "tool_calls": [
                    {"id": "call_1", "name": "list_mitoflow_modules", "arguments": {}},
                ],
            },
            {"content": "MitoFlow includes annotate, qc, viz, and other modules."},
        ]
    )
    service = AIService(
        session_root=tmp_path / "sessions",
        workspace_root=tmp_path,
        registry=registry,
        provider=provider,
        model="fake",
    )
    session_id = service.create_session()

    result = service.send_message(
        session_id=session_id,
        message="What can MitoFlow do?",
        entry_point=EntryPoint.CLI,
    )

    assert "annotate" in result.final_text
    assert result.tool_results[0].name == "list_mitoflow_modules"


def test_service_list_tools(tmp_path):
    service = AIService(
        session_root=tmp_path / "sessions",
        workspace_root=tmp_path,
        provider=FakeProvider(responses=[{"content": "ok"}]),
        model="fake",
    )

    tools = service.list_tools(EntryPoint.CLI)
    names = {tool["name"] for tool in tools}

    assert "list_mitoflow_modules" in names
