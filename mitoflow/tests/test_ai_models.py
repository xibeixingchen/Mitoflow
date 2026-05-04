"""Tests for provider-neutral AI models."""

from mitoflow.ai.models import (
    AIMessage,
    EntryPoint,
    ProviderResponse,
    SafetyLevel,
    ToolCall,
    ToolDefinition,
)


def test_tool_definition_serializes_for_schema():
    tool = ToolDefinition(
        name="list_modules",
        description="List modules",
        parameters={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        safety_level=SafetyLevel.READ_ONLY,
        entry_points=[EntryPoint.CLI, EntryPoint.API],
    )

    dumped = tool.model_dump(mode="json")

    assert dumped["name"] == "list_modules"
    assert dumped["safety_level"] == "read_only"
    assert dumped["entry_points"] == ["cli", "api"]


def test_provider_response_can_hold_tool_calls():
    response = ProviderResponse(
        message=AIMessage(role="assistant", content="I will inspect the results."),
        tool_calls=[
            ToolCall(
                id="call_1",
                name="summarize_result_directory",
                arguments={"path": "results/sample"},
            )
        ],
        stop_reason="tool_calls",
        usage={"input_tokens": 10, "output_tokens": 5},
    )

    assert response.tool_calls[0].name == "summarize_result_directory"
    assert response.usage["output_tokens"] == 5


def test_ai_message_roles():
    for role in ("system", "user", "assistant", "tool"):
        msg = AIMessage(role=role, content="test")
        assert msg.role == role


def test_tool_call_defaults():
    call = ToolCall(id="c1", name="echo")
    assert call.arguments == {}
