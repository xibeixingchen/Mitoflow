"""Tests for AI provider adapters."""

from types import SimpleNamespace

from mitoflow.ai.models import AIMessage, ProviderRequest, SafetyLevel, ToolDefinition
from mitoflow.ai.providers import FakeProvider


def test_fake_provider_returns_scripted_tool_call():
    provider = FakeProvider(
        responses=[
            {
                "content": "Inspecting.",
                "tool_calls": [
                    {"id": "call_1", "name": "list_modules", "arguments": {}},
                ],
            }
        ]
    )
    request = ProviderRequest(model="fake", messages=[AIMessage(role="user", content="hello")])

    response = provider.create(request)

    assert response.message.content == "Inspecting."
    assert response.tool_calls[0].name == "list_modules"


def test_fake_provider_returns_final_text():
    provider = FakeProvider(responses=[{"content": "Hello! How can I help?"}])
    request = ProviderRequest(model="fake", messages=[AIMessage(role="user", content="hi")])

    response = provider.create(request)

    assert response.message.content == "Hello! How can I help?"
    assert response.tool_calls == []
    assert response.stop_reason == "stop"


def test_fake_provider_tracks_requests():
    provider = FakeProvider(responses=[{"content": "ok"}])
    request = ProviderRequest(model="fake", messages=[AIMessage(role="user", content="test")])

    provider.create(request)

    assert len(provider.requests) == 1
    assert provider.requests[0].messages[0].content == "test"


def test_fake_provider_handles_empty_responses():
    provider = FakeProvider(responses=[])
    request = ProviderRequest(model="fake", messages=[AIMessage(role="user", content="hello")])

    response = provider.create(request)

    assert "No scripted response" in response.message.content
