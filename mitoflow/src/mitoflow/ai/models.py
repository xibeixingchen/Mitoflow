"""Provider-neutral data models for MitoFlow AI."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SafetyLevel(str, Enum):
    """Safety classification for registered tools."""

    READ_ONLY = "read_only"
    WRITES_OUTPUT = "writes_output"
    LAUNCHES_JOB = "launches_job"
    EXTERNAL_NETWORK = "external_network"
    DESTRUCTIVE = "destructive"


class EntryPoint(str, Enum):
    """Application entry points allowed to call tools."""

    CLI = "cli"
    API = "api"
    WEB = "web"


class ToolCall(BaseModel):
    """A normalized model-requested tool call."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AIMessage(BaseModel):
    """A provider-neutral chat message."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None


class ToolDefinition(BaseModel):
    """A tool schema exposed to model providers."""

    name: str
    description: str
    parameters: dict[str, Any]
    safety_level: SafetyLevel = SafetyLevel.READ_ONLY
    entry_points: list[EntryPoint] = Field(default_factory=lambda: [EntryPoint.CLI])


class ToolResult(BaseModel):
    """Structured result returned by a tool executor."""

    call_id: str
    name: str
    ok: bool
    content: str
    data: dict[str, Any] = Field(default_factory=dict)


class ProviderRequest(BaseModel):
    """Provider-neutral request sent to an adapter."""

    model: str
    messages: list[AIMessage]
    tools: list[ToolDefinition] = Field(default_factory=list)
    temperature: float = 0.1
    max_tokens: int = 2048


class ProviderResponse(BaseModel):
    """Provider-neutral response returned by an adapter."""

    message: AIMessage
    tool_calls: list[ToolCall] = Field(default_factory=list)
    stop_reason: str = "stop"
    usage: dict[str, Any] = Field(default_factory=dict)


class RuntimeEvent(BaseModel):
    """Trace event emitted by the runtime."""

    type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class RuntimeResult(BaseModel):
    """Final result returned by a runtime turn."""

    session_id: str
    final_text: str
    messages: list[AIMessage]
    events: list[RuntimeEvent] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    usage: dict[str, Any] = Field(default_factory=dict)
