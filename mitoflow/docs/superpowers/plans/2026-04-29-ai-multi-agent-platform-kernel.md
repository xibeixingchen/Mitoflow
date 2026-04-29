# AI Multi-Agent Platform Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first MitoFlow AI platform kernel with shared CLI, FastAPI, and Streamlit entry points, plus OpenAI and Anthropic provider adapters.

**Architecture:** Add a new `mitoflow.ai` package that owns provider-neutral messages, tool registry, local sessions, the manager runtime loop, and initial MitoFlow tool wrappers. Existing CLI/Web entry points become thin callers into this shared service so protocol logic and tool safety are not duplicated.

**Tech Stack:** Python 3.10+, Pydantic v2, Typer, Rich, FastAPI, Streamlit, pytest, optional `openai` and `anthropic` SDKs.

---

## File Structure

Create these files:

- `src/mitoflow/ai/__init__.py` - public exports for the AI package.
- `src/mitoflow/ai/models.py` - provider-neutral Pydantic models and enums.
- `src/mitoflow/ai/prompts.py` - manager and summarizer prompts.
- `src/mitoflow/ai/tools.py` - registry, execution context, and path-safety helpers.
- `src/mitoflow/ai/sessions.py` - local JSONL session store.
- `src/mitoflow/ai/providers.py` - fake, OpenAI, and Anthropic adapters.
- `src/mitoflow/ai/runtime.py` - manager loop for tool calls and final answers.
- `src/mitoflow/ai/mitoflow_tools.py` - first allowlisted MitoFlow tools.
- `src/mitoflow/ai/service.py` - shared service builder used by CLI/API/Web.
- `tests/test_ai_models.py` - model serialization tests.
- `tests/test_ai_tools.py` - registry and path validation tests.
- `tests/test_ai_sessions.py` - JSONL session persistence tests.
- `tests/test_ai_runtime.py` - fake-provider full loop tests.
- `tests/test_ai_providers.py` - provider conversion tests.
- `tests/test_ai_service.py` - service-level tests.

Modify these files:

- `pyproject.toml` - add optional AI/Web/dev dependencies.
- `src/mitoflow/cli.py` - add `mitoflow ai-chat`.
- `deploy/web/backend/main.py` - add `/api/ai/*` endpoints.
- `deploy/web/frontend/app.py` - add AI Chat tab and API helpers.
- `deploy/docker/Dockerfile.web` - install AI optional dependencies.
- `deploy/docker/docker-compose.yml` - pass AI provider environment variables through to backend/frontend.

Design boundaries:

- Provider adapters normalize model protocols into internal `AIMessage`, `ToolCall`, and `ProviderResponse` objects.
- `AgentRuntime` is synchronous in phase one to match the current MitoFlow pipeline style.
- Web endpoints are added to the existing FastAPI prototype without replacing its current annotation endpoints.
- Tool wrappers only expose allowlisted Python functions. They do not execute arbitrary shell commands from model output.

---

### Task 1: AI Core Models, Prompts, Tool Registry, and Session Store

**Files:**
- Create: `src/mitoflow/ai/__init__.py`
- Create: `src/mitoflow/ai/models.py`
- Create: `src/mitoflow/ai/prompts.py`
- Create: `src/mitoflow/ai/tools.py`
- Create: `src/mitoflow/ai/sessions.py`
- Test: `tests/test_ai_models.py`
- Test: `tests/test_ai_tools.py`
- Test: `tests/test_ai_sessions.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_ai_models.py`:

```python
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
```

- [ ] **Step 2: Write failing registry and path-safety tests**

Create `tests/test_ai_tools.py`:

```python
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
```

- [ ] **Step 3: Write failing session store tests**

Create `tests/test_ai_sessions.py`:

```python
"""Tests for local AI session persistence."""

from mitoflow.ai.models import AIMessage, RuntimeEvent
from mitoflow.ai.sessions import LocalSessionStore


def test_session_store_creates_and_loads_messages(tmp_path):
    store = LocalSessionStore(tmp_path)
    session_id = store.create_session()
    store.append_message(session_id, AIMessage(role="user", content="hello"))
    store.append_message(session_id, AIMessage(role="assistant", content="hi"))

    messages = store.load_messages(session_id)

    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].content == "hello"


def test_session_store_records_events(tmp_path):
    store = LocalSessionStore(tmp_path)
    session_id = store.create_session()
    store.append_event(
        session_id,
        RuntimeEvent(type="tool_result", message="Tool completed", data={"ok": True}),
    )

    events = store.load_events(session_id)

    assert events[0].type == "tool_result"
    assert events[0].data == {"ok": True}
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ai_models.py tests/test_ai_tools.py tests/test_ai_sessions.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'mitoflow.ai'`.

- [ ] **Step 5: Create AI package exports**

Create `src/mitoflow/ai/__init__.py`:

```python
"""AI orchestration layer for MitoFlow."""

from .models import (
    AIMessage,
    EntryPoint,
    ProviderRequest,
    ProviderResponse,
    RuntimeEvent,
    RuntimeResult,
    SafetyLevel,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from .sessions import LocalSessionStore
from .tools import ToolContext, ToolRegistry

__all__ = [
    "AIMessage",
    "EntryPoint",
    "LocalSessionStore",
    "ProviderRequest",
    "ProviderResponse",
    "RuntimeEvent",
    "RuntimeResult",
    "SafetyLevel",
    "ToolCall",
    "ToolContext",
    "ToolDefinition",
    "ToolRegistry",
    "ToolResult",
]
```

- [ ] **Step 6: Create provider-neutral models**

Create `src/mitoflow/ai/models.py`:

```python
"""Provider-neutral data models for MitoFlow AI."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SafetyLevel(StrEnum):
    """Safety classification for registered tools."""

    READ_ONLY = "read_only"
    WRITES_OUTPUT = "writes_output"
    LAUNCHES_JOB = "launches_job"
    EXTERNAL_NETWORK = "external_network"
    DESTRUCTIVE = "destructive"


class EntryPoint(StrEnum):
    """Application entry points allowed to call tools."""

    CLI = "cli"
    API = "api"
    WEB = "web"


class AIMessage(BaseModel):
    """A provider-neutral chat message."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None


class ToolCall(BaseModel):
    """A normalized model-requested tool call."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


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
```

- [ ] **Step 7: Create prompts**

Create `src/mitoflow/ai/prompts.py`:

```python
"""System prompts for MitoFlow AI agents."""

from __future__ import annotations


MANAGER_SYSTEM_PROMPT = """You are MitoFlow AI, a scientific assistant for plant organelle genomics.

You help users run and interpret MitoFlow workflows for plant mitochondrial genomes, and you can route future chloroplast and pan-organelle workflows when tools are registered.

Rules:
- Use registered tools for file inspection, pipeline execution, and result summaries.
- Do not invent output files, metrics, or biological conclusions that are not present in tool results.
- Ask for clarification when the organism, input file, or requested workflow is ambiguous.
- Keep public-service safety in mind: never request arbitrary shell execution.
- Treat generated biological interpretations as analysis support that requires expert review.
"""


RESULT_SUMMARY_PROMPT = """Summarize tool outputs for a plant organelle genomics user.

Focus on:
- what was run;
- what files or artifacts were produced;
- important warnings or missing inputs;
- practical next steps.

Avoid overstating biological conclusions beyond the available outputs.
"""
```

- [ ] **Step 8: Create tool registry and path-safety helpers**

Create `src/mitoflow/ai/tools.py`:

```python
"""Tool registry and execution safety for MitoFlow AI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import EntryPoint, ToolCall, ToolDefinition, ToolResult

ToolExecutor = Callable[[dict[str, Any], "ToolContext"], dict[str, Any] | ToolResult]


class ToolContext(BaseModel):
    """Runtime context passed to tool executors."""

    session_id: str
    workspace_root: Path
    output_root: Path
    entry_point: EntryPoint

    class Config:
        arbitrary_types_allowed = True


def ensure_under_root(path: Path | str, root: Path | str) -> Path:
    """Resolve a path and require it to stay under the configured root."""
    resolved = Path(path).expanduser().resolve()
    root_resolved = Path(root).expanduser().resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Path {resolved} is outside allowed root {root_resolved}") from exc
    return resolved


class ToolRegistry:
    """Registry for allowlisted AI tools."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._executors: dict[str, ToolExecutor] = {}

    def register(self, definition: ToolDefinition, executor: ToolExecutor) -> None:
        """Register a tool definition and executor."""
        if definition.name in self._definitions:
            raise ValueError(f"Tool '{definition.name}' is already registered")
        self._definitions[definition.name] = definition
        self._executors[definition.name] = executor

    def definitions(self, entry_point: EntryPoint | None = None) -> list[ToolDefinition]:
        """List tool definitions, optionally filtered by entry point."""
        values = list(self._definitions.values())
        if entry_point is None:
            return values
        return [tool for tool in values if entry_point in tool.entry_points]

    def get(self, name: str) -> ToolDefinition:
        """Return one tool definition."""
        if name not in self._definitions:
            raise KeyError(name)
        return self._definitions[name]

    def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:
        """Execute a tool call with entry-point enforcement."""
        if call.name not in self._definitions:
            return ToolResult(
                call_id=call.id,
                name=call.name,
                ok=False,
                content=f"Tool '{call.name}' is not registered.",
            )

        definition = self._definitions[call.name]
        if context.entry_point not in definition.entry_points:
            return ToolResult(
                call_id=call.id,
                name=call.name,
                ok=False,
                content=f"Tool '{call.name}' is not available for {context.entry_point.value}.",
            )

        try:
            raw = self._executors[call.name](call.arguments, context)
        except Exception as exc:
            return ToolResult(
                call_id=call.id,
                name=call.name,
                ok=False,
                content=f"Tool '{call.name}' failed: {exc}",
            )

        if isinstance(raw, ToolResult):
            return raw

        content = str(raw.get("content", raw))
        data = raw.get("data", raw)
        if not isinstance(data, dict):
            data = {"value": data}
        return ToolResult(
            call_id=call.id,
            name=call.name,
            ok=True,
            content=content,
            data=data,
        )
```

- [ ] **Step 9: Create local session store**

Create `src/mitoflow/ai/sessions.py`:

```python
"""Local JSONL session storage for MitoFlow AI."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .models import AIMessage, RuntimeEvent

T = TypeVar("T", bound=BaseModel)


class LocalSessionStore:
    """Persist chat messages and runtime events under a local directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_session(self) -> str:
        """Create a session directory and return its id."""
        session_id = str(uuid.uuid4())
        self._session_dir(session_id).mkdir(parents=True, exist_ok=False)
        (self._session_dir(session_id) / "artifacts").mkdir(parents=True, exist_ok=True)
        return session_id

    def session_exists(self, session_id: str) -> bool:
        """Return whether a session exists."""
        return self._session_dir(session_id).exists()

    def artifact_dir(self, session_id: str) -> Path:
        """Return the artifact directory for a session."""
        path = self._session_dir(session_id) / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def append_message(self, session_id: str, message: AIMessage) -> None:
        """Append one message to a session."""
        self._append_model(self._messages_path(session_id), message)

    def load_messages(self, session_id: str) -> list[AIMessage]:
        """Load all messages for a session."""
        return self._load_models(self._messages_path(session_id), AIMessage)

    def append_event(self, session_id: str, event: RuntimeEvent) -> None:
        """Append one runtime event to a session."""
        self._append_model(self._events_path(session_id), event)

    def load_events(self, session_id: str) -> list[RuntimeEvent]:
        """Load all runtime events for a session."""
        return self._load_models(self._events_path(session_id), RuntimeEvent)

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _messages_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "messages.jsonl"

    def _events_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "events.jsonl"

    def _append_model(self, path: Path, value: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value.model_dump(mode="json"), ensure_ascii=True) + "\n")

    def _load_models(self, path: Path, model_type: type[T]) -> list[T]:
        if not path.exists():
            return []
        values: list[T] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    values.append(model_type.model_validate(json.loads(line)))
        return values
```

- [ ] **Step 10: Run core tests**

Run:

```bash
pytest tests/test_ai_models.py tests/test_ai_tools.py tests/test_ai_sessions.py -v
```

Expected: PASS.

- [ ] **Step 11: Commit Task 1**

Run:

```bash
git add src/mitoflow/ai/__init__.py src/mitoflow/ai/models.py src/mitoflow/ai/prompts.py src/mitoflow/ai/tools.py src/mitoflow/ai/sessions.py tests/test_ai_models.py tests/test_ai_tools.py tests/test_ai_sessions.py
git commit -m "feat(ai): add core runtime models and tool registry"
```

---

### Task 2: Provider Adapters and Runtime Loop

**Files:**
- Create: `src/mitoflow/ai/providers.py`
- Create: `src/mitoflow/ai/runtime.py`
- Modify: `src/mitoflow/ai/__init__.py`
- Test: `tests/test_ai_providers.py`
- Test: `tests/test_ai_runtime.py`

- [ ] **Step 1: Write failing provider adapter tests**

Create `tests/test_ai_providers.py`:

```python
"""Tests for AI provider adapters."""

from types import SimpleNamespace

from mitoflow.ai.models import AIMessage, ProviderRequest, SafetyLevel, ToolDefinition
from mitoflow.ai.providers import AnthropicAdapter, FakeProvider, OpenAIChatAdapter


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


def test_openai_adapter_formats_tools():
    adapter = OpenAIChatAdapter(api_key="test", model="gpt-test", client=None)
    tool = ToolDefinition(
        name="list_modules",
        description="List modules",
        parameters={"type": "object", "properties": {}},
        safety_level=SafetyLevel.READ_ONLY,
    )

    formatted = adapter.format_tools([tool])

    assert formatted[0]["type"] == "function"
    assert formatted[0]["function"]["name"] == "list_modules"


def test_anthropic_adapter_formats_tools():
    adapter = AnthropicAdapter(api_key="test", model="claude-test", client=None)
    tool = ToolDefinition(
        name="list_modules",
        description="List modules",
        parameters={"type": "object", "properties": {}},
        safety_level=SafetyLevel.READ_ONLY,
    )

    formatted = adapter.format_tools([tool])

    assert formatted[0]["name"] == "list_modules"
    assert formatted[0]["input_schema"]["type"] == "object"


def test_openai_adapter_parses_tool_calls():
    adapter = OpenAIChatAdapter(api_key="test", model="gpt-test", client=None)
    raw = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(
                                name="list_modules",
                                arguments="{}",
                            ),
                        )
                    ],
                ),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=3, completion_tokens=4, total_tokens=7),
    )

    response = adapter.parse_response(raw)

    assert response.tool_calls[0].id == "call_1"
    assert response.usage["total_tokens"] == 7
```

- [ ] **Step 2: Write failing runtime loop tests**

Create `tests/test_ai_runtime.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ai_providers.py tests/test_ai_runtime.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `mitoflow.ai.providers` or `mitoflow.ai.runtime`.

- [ ] **Step 4: Implement provider adapters**

Create `src/mitoflow/ai/providers.py`:

```python
"""Provider adapters for OpenAI-compatible and Anthropic Claude APIs."""

from __future__ import annotations

import json
from typing import Any, Protocol

from .models import AIMessage, ProviderRequest, ProviderResponse, ToolCall, ToolDefinition


class ProviderAdapter(Protocol):
    """Protocol implemented by all model providers."""

    def create(self, request: ProviderRequest) -> ProviderResponse:
        """Create one response."""


class FakeProvider:
    """Scripted provider for tests and offline development."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: list[ProviderRequest] = []

    def create(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if not self.responses:
            payload = {"content": "No scripted response available."}
        else:
            payload = self.responses.pop(0)
        calls = [
            ToolCall(
                id=str(item["id"]),
                name=str(item["name"]),
                arguments=dict(item.get("arguments", {})),
            )
            for item in payload.get("tool_calls", [])
        ]
        return ProviderResponse(
            message=AIMessage(role="assistant", content=str(payload.get("content", ""))),
            tool_calls=calls,
            stop_reason="tool_calls" if calls else "stop",
            usage=dict(payload.get("usage", {})),
        )


class OpenAIChatAdapter:
    """Adapter for OpenAI Chat Completions compatible APIs."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        if client is not None:
            self.client = client
        else:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install the 'openai' package to use the OpenAI provider") from exc
            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = OpenAI(**kwargs)

    def create(self, request: ProviderRequest) -> ProviderResponse:
        raw = self.client.chat.completions.create(
            model=request.model or self.model,
            messages=self.format_messages(request.messages),
            tools=self.format_tools(request.tools) if request.tools else None,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return self.parse_response(raw)

    def format_messages(self, messages: list[AIMessage]) -> list[dict[str, Any]]:
        formatted: list[dict[str, Any]] = []
        for message in messages:
            item: dict[str, Any] = {"role": message.role, "content": message.content}
            if message.name:
                item["name"] = message.name
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            formatted.append(item)
        return formatted

    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in tools
        ]

    def parse_response(self, raw: Any) -> ProviderResponse:
        choice = raw.choices[0]
        message = choice.message
        calls: list[ToolCall] = []
        for call in getattr(message, "tool_calls", None) or []:
            arguments_raw = call.function.arguments or "{}"
            try:
                arguments = json.loads(arguments_raw)
            except json.JSONDecodeError:
                arguments = {"_raw": arguments_raw}
            calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))

        usage = getattr(raw, "usage", None)
        usage_data = {}
        if usage is not None:
            usage_data = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }

        return ProviderResponse(
            message=AIMessage(role="assistant", content=getattr(message, "content", "") or ""),
            tool_calls=calls,
            stop_reason=getattr(choice, "finish_reason", "stop") or "stop",
            usage=usage_data,
        )


class AnthropicAdapter:
    """Adapter for native Anthropic Messages API."""

    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        self.model = model
        if client is not None:
            self.client = client
        else:
            try:
                import anthropic
            except ImportError as exc:
                raise RuntimeError("Install the 'anthropic' package to use the Anthropic provider") from exc
            self.client = anthropic.Anthropic(api_key=api_key)

    def create(self, request: ProviderRequest) -> ProviderResponse:
        system, messages = self.format_messages(request.messages)
        kwargs: dict[str, Any] = {
            "model": request.model or self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if request.tools:
            kwargs["tools"] = self.format_tools(request.tools)
        raw = self.client.messages.create(**kwargs)
        return self.parse_response(raw)

    def format_messages(self, messages: list[AIMessage]) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts: list[str] = []
        formatted: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
            elif message.role == "tool":
                formatted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id or message.name or "tool",
                                "content": message.content,
                            }
                        ],
                    }
                )
            else:
                formatted.append({"role": message.role, "content": message.content})
        return ("\n".join(system_parts) if system_parts else None), formatted

    def format_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    def parse_response(self, raw: Any) -> ProviderResponse:
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in getattr(raw, "content", []) or []:
            block_type = getattr(block, "type", "")
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
            elif block_type == "tool_use":
                calls.append(
                    ToolCall(
                        id=getattr(block, "id"),
                        name=getattr(block, "name"),
                        arguments=dict(getattr(block, "input", {}) or {}),
                    )
                )

        usage = getattr(raw, "usage", None)
        usage_data = {}
        if usage is not None:
            usage_data = {
                "input_tokens": getattr(usage, "input_tokens", 0),
                "output_tokens": getattr(usage, "output_tokens", 0),
            }

        return ProviderResponse(
            message=AIMessage(role="assistant", content="".join(text_parts)),
            tool_calls=calls,
            stop_reason=getattr(raw, "stop_reason", "stop") or "stop",
            usage=usage_data,
        )
```

- [ ] **Step 5: Implement runtime loop**

Create `src/mitoflow/ai/runtime.py`:

```python
"""Manager runtime loop for MitoFlow AI."""

from __future__ import annotations

from .models import AIMessage, ProviderRequest, RuntimeEvent, RuntimeResult, ToolResult
from .prompts import MANAGER_SYSTEM_PROMPT
from .providers import ProviderAdapter
from .sessions import LocalSessionStore
from .tools import ToolContext, ToolRegistry


class AgentRuntime:
    """Synchronous manager-agent loop for one chat turn."""

    def __init__(
        self,
        provider: ProviderAdapter,
        registry: ToolRegistry,
        store: LocalSessionStore,
        model: str,
        max_turns: int = 6,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.store = store
        self.model = model
        self.max_turns = max_turns

    def run_turn(self, session_id: str, user_text: str, context: ToolContext) -> RuntimeResult:
        """Run one user turn, including any model-requested tool calls."""
        if not self.store.session_exists(session_id):
            raise ValueError(f"Unknown AI session: {session_id}")

        user_message = AIMessage(role="user", content=user_text)
        self.store.append_message(session_id, user_message)

        events: list[RuntimeEvent] = []
        tool_results: list[ToolResult] = []
        usage: dict[str, int] = {}

        for turn_index in range(self.max_turns):
            messages = self._messages_with_system(session_id)
            response = self.provider.create(
                ProviderRequest(
                    model=self.model,
                    messages=messages,
                    tools=self.registry.definitions(context.entry_point),
                )
            )
            self.store.append_message(session_id, response.message)
            self._merge_usage(usage, response.usage)

            if not response.tool_calls:
                event = RuntimeEvent(
                    type="assistant_final",
                    message="Assistant returned a final answer.",
                    data={"turn_index": turn_index},
                )
                self.store.append_event(session_id, event)
                events.append(event)
                return RuntimeResult(
                    session_id=session_id,
                    final_text=response.message.content,
                    messages=self.store.load_messages(session_id),
                    events=self.store.load_events(session_id),
                    tool_results=tool_results,
                    usage=usage,
                )

            for call in response.tool_calls:
                event = RuntimeEvent(
                    type="tool_call",
                    message=f"Calling tool {call.name}",
                    data=call.model_dump(mode="json"),
                )
                self.store.append_event(session_id, event)
                events.append(event)

                result = self.registry.execute(call, context)
                tool_results.append(result)
                result_event = RuntimeEvent(
                    type="tool_result",
                    message=result.content,
                    data=result.model_dump(mode="json"),
                )
                self.store.append_event(session_id, result_event)
                events.append(result_event)
                self.store.append_message(
                    session_id,
                    AIMessage(
                        role="tool",
                        name=result.name,
                        tool_call_id=result.call_id,
                        content=result.content,
                    ),
                )

        final_text = "Stopped after reaching maximum tool turns without a final answer."
        self.store.append_message(session_id, AIMessage(role="assistant", content=final_text))
        return RuntimeResult(
            session_id=session_id,
            final_text=final_text,
            messages=self.store.load_messages(session_id),
            events=self.store.load_events(session_id),
            tool_results=tool_results,
            usage=usage,
        )

    def _messages_with_system(self, session_id: str) -> list[AIMessage]:
        messages = self.store.load_messages(session_id)
        if messages and messages[0].role == "system":
            return messages
        return [AIMessage(role="system", content=MANAGER_SYSTEM_PROMPT), *messages]

    def _merge_usage(self, target: dict[str, int], source: dict[str, object]) -> None:
        for key, value in source.items():
            if isinstance(value, int):
                target[key] = target.get(key, 0) + value
```

- [ ] **Step 6: Update exports**

Modify `src/mitoflow/ai/__init__.py` to import providers and runtime after they exist:

```python
from .providers import AnthropicAdapter, FakeProvider, OpenAIChatAdapter
from .runtime import AgentRuntime
```

Add these names to `__all__`:

```python
"AgentRuntime",
"AnthropicAdapter",
"FakeProvider",
"OpenAIChatAdapter",
```

- [ ] **Step 7: Run runtime and provider tests**

Run:

```bash
pytest tests/test_ai_providers.py tests/test_ai_runtime.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add src/mitoflow/ai/__init__.py src/mitoflow/ai/providers.py src/mitoflow/ai/runtime.py tests/test_ai_providers.py tests/test_ai_runtime.py
git commit -m "feat(ai): add provider adapters and runtime loop"
```

---

### Task 3: MitoFlow Tool Wrappers and Shared AI Service

**Files:**
- Create: `src/mitoflow/ai/mitoflow_tools.py`
- Create: `src/mitoflow/ai/service.py`
- Modify: `src/mitoflow/ai/__init__.py`
- Test: `tests/test_ai_service.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_ai_service.py`:

```python
"""Tests for AI service and default MitoFlow tools."""

from mitoflow.ai.models import EntryPoint
from mitoflow.ai.providers import FakeProvider
from mitoflow.ai.service import AIService, build_default_registry


def test_default_registry_has_core_tools():
    registry = build_default_registry()
    names = {tool.name for tool in registry.definitions(EntryPoint.CLI)}

    assert "list_mitoflow_modules" in names
    assert "summarize_result_directory" in names


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ai_service.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `mitoflow.ai.service`.

- [ ] **Step 3: Implement default tool wrappers**

Create `src/mitoflow/ai/mitoflow_tools.py`:

```python
"""Allowlisted MitoFlow tools for AI orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import EntryPoint, SafetyLevel, ToolDefinition
from .tools import ToolContext, ToolRegistry, ensure_under_root


MITOFLOW_MODULES = [
    "annotate",
    "qc",
    "viz",
    "mtpt",
    "rna-edit",
    "codon",
    "multiconf",
    "kaks",
    "synteny",
    "pi",
    "phylo",
    "cms",
    "validate-rna",
    "report",
    "repeat",
    "numt",
    "gc",
    "phylo-tree",
]


def register_mitoflow_tools(registry: ToolRegistry) -> None:
    """Register the first safe MitoFlow AI tools."""
    registry.register(
        ToolDefinition(
            name="list_mitoflow_modules",
            description="List currently available MitoFlow analysis modules.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        list_mitoflow_modules,
    )
    registry.register(
        ToolDefinition(
            name="summarize_result_directory",
            description="Inspect a MitoFlow result directory and summarize known output files.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path under the configured workspace root."}
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        summarize_result_directory,
    )
    registry.register(
        ToolDefinition(
            name="run_annotation",
            description="Run the existing MitoFlow annotation pipeline on a FASTA file under the workspace root.",
            parameters={
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                    "name": {"type": "string"},
                    "threads": {"type": "integer", "minimum": 1, "maximum": 16},
                    "skip_trna": {"type": "boolean"},
                    "skip_rrna": {"type": "boolean"},
                    "skip_qc": {"type": "boolean"},
                },
                "required": ["input"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.LAUNCHES_JOB,
            entry_points=[EntryPoint.CLI, EntryPoint.API],
        ),
        run_annotation,
    )


def list_mitoflow_modules(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Return module names and a compact summary."""
    return {
        "content": "Available MitoFlow modules: " + ", ".join(MITOFLOW_MODULES),
        "data": {"modules": MITOFLOW_MODULES},
    }


def summarize_result_directory(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Summarize known files under a MitoFlow output directory."""
    path = ensure_under_root(args["path"], context.workspace_root)
    if not path.exists():
        raise FileNotFoundError(path)
    if not path.is_dir():
        raise ValueError(f"Expected a directory: {path}")

    known_dirs = ["gff", "genbank", "fasta", "report", "results"]
    summary: dict[str, list[str]] = {}
    for dirname in known_dirs:
        subdir = path / dirname
        if subdir.exists() and subdir.is_dir():
            summary[dirname] = sorted(item.name for item in subdir.iterdir() if item.is_file())[:50]

    top_level = sorted(item.name for item in path.iterdir())[:50]
    content = f"Found result directory {path.name} with entries: {', '.join(top_level)}"
    return {"content": content, "data": {"path": str(path), "top_level": top_level, "known_outputs": summary}}


def run_annotation(args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Run AnnotationPipeline synchronously into a session output directory."""
    from ..core.pipeline import AnnotationPipeline

    fasta_path = ensure_under_root(args["input"], context.workspace_root)
    if not fasta_path.exists():
        raise FileNotFoundError(fasta_path)

    name = str(args.get("name") or fasta_path.stem)
    threads = int(args.get("threads") or 4)
    output_dir = context.output_root / "annotation" / name
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline = AnnotationPipeline(threads=threads)
    result = pipeline.run(
        fasta_path=fasta_path,
        output_dir=output_dir,
        name=name,
        skip_trna=bool(args.get("skip_trna", False)),
        skip_rrna=bool(args.get("skip_rrna", False)),
        skip_qc=bool(args.get("skip_qc", False)),
        skip_mtpt=True,
    )
    return {
        "content": f"Annotation completed for {name}. {result.summary()}",
        "data": {
            "output_dir": str(output_dir),
            "summary": result.summary(),
            "warnings": result.warnings,
        },
    }
```

- [ ] **Step 4: Implement AI service builder**

Create `src/mitoflow/ai/service.py`:

```python
"""Application-facing AI service for CLI, API, and Web entry points."""

from __future__ import annotations

import os
from pathlib import Path

from .mitoflow_tools import register_mitoflow_tools
from .models import EntryPoint, RuntimeResult
from .providers import AnthropicAdapter, FakeProvider, OpenAIChatAdapter, ProviderAdapter
from .runtime import AgentRuntime
from .sessions import LocalSessionStore
from .tools import ToolContext, ToolRegistry


def build_default_registry() -> ToolRegistry:
    """Build the default allowlisted registry."""
    registry = ToolRegistry()
    register_mitoflow_tools(registry)
    return registry


def build_provider(provider_name: str | None = None, model: str | None = None) -> tuple[ProviderAdapter, str]:
    """Build a provider from environment configuration."""
    provider = (provider_name or os.getenv("MITOFLOW_AI_PROVIDER") or "fake").lower()
    if provider == "fake":
        return FakeProvider(responses=[{"content": "MitoFlow AI is configured with the fake provider."}]), model or "fake"
    if provider == "openai":
        selected_model = model or os.getenv("OPENAI_MODEL") or "gpt-5.2"
        return (
            OpenAIChatAdapter(
                api_key=os.environ["OPENAI_API_KEY"],
                model=selected_model,
                base_url=os.getenv("OPENAI_BASE_URL"),
            ),
            selected_model,
        )
    if provider == "anthropic":
        selected_model = model or os.getenv("ANTHROPIC_MODEL") or "claude-opus-4-1-20250805"
        return AnthropicAdapter(api_key=os.environ["ANTHROPIC_API_KEY"], model=selected_model), selected_model
    raise ValueError(f"Unsupported AI provider: {provider}")


class AIService:
    """Shared service used by CLI, API, and Web layers."""

    def __init__(
        self,
        session_root: Path | str,
        workspace_root: Path | str,
        registry: ToolRegistry | None = None,
        provider: ProviderAdapter | None = None,
        model: str | None = None,
    ) -> None:
        self.store = LocalSessionStore(session_root)
        self.workspace_root = Path(workspace_root).resolve()
        self.registry = registry or build_default_registry()
        if provider is None:
            provider, resolved_model = build_provider(model=model)
            self.provider = provider
            self.model = resolved_model
        else:
            self.provider = provider
            self.model = model or "fake"

    def create_session(self) -> str:
        """Create a chat session."""
        return self.store.create_session()

    def list_tools(self, entry_point: EntryPoint) -> list[dict[str, object]]:
        """List tools available for an entry point."""
        return [tool.model_dump(mode="json") for tool in self.registry.definitions(entry_point)]

    def send_message(
        self,
        session_id: str,
        message: str,
        entry_point: EntryPoint,
    ) -> RuntimeResult:
        """Send a user message through the runtime."""
        context = ToolContext(
            session_id=session_id,
            workspace_root=self.workspace_root,
            output_root=self.store.artifact_dir(session_id),
            entry_point=entry_point,
        )
        runtime = AgentRuntime(
            provider=self.provider,
            registry=self.registry,
            store=self.store,
            model=self.model,
        )
        return runtime.run_turn(session_id=session_id, user_text=message, context=context)
```

- [ ] **Step 5: Update exports**

Modify `src/mitoflow/ai/__init__.py`:

```python
from .service import AIService, build_default_registry, build_provider
```

Add to `__all__`:

```python
"AIService",
"build_default_registry",
"build_provider",
```

- [ ] **Step 6: Run service tests**

Run:

```bash
pytest tests/test_ai_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add src/mitoflow/ai/__init__.py src/mitoflow/ai/mitoflow_tools.py src/mitoflow/ai/service.py tests/test_ai_service.py
git commit -m "feat(ai): register core mitoflow tools"
```

---

### Task 4: CLI Entry Point

**Files:**
- Modify: `src/mitoflow/cli.py:9-15`
- Test: `tests/test_ai_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_ai_cli.py`:

```python
"""Tests for MitoFlow AI CLI entry point."""

from typer.testing import CliRunner

from mitoflow.cli import app


def test_ai_chat_one_shot_fake_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("MITOFLOW_AI_PROVIDER", "fake")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "ai-chat",
            "--prompt",
            "hello",
            "--sessions-dir",
            str(tmp_path / "sessions"),
            "--workspace",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "MitoFlow AI is configured with the fake provider" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_cli.py -v
```

Expected: FAIL because `ai-chat` is not registered.

- [ ] **Step 3: Add CLI command**

Modify `src/mitoflow/cli.py` after line 15:

```python

@app.command(name="ai-chat")
def ai_chat(
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="One-shot prompt. Omit for interactive mode."),
    provider: Optional[str] = typer.Option(None, "--provider", help="Provider: fake | openai | anthropic"),
    model: Optional[str] = typer.Option(None, "--model", help="Provider model name"),
    session: Optional[str] = typer.Option(None, "--session", help="Existing AI session id"),
    sessions_dir: Path = typer.Option(Path(".mitoflow_ai_sessions"), "--sessions-dir", help="Local AI session directory"),
    workspace: Path = typer.Option(Path("."), "--workspace", help="Allowed workspace root for AI tools"),
):
    """Chat with the MitoFlow AI multi-agent runtime."""
    from .ai.models import EntryPoint
    from .ai.service import AIService, build_provider

    resolved_provider, resolved_model = build_provider(provider_name=provider, model=model)
    service = AIService(
        session_root=sessions_dir,
        workspace_root=workspace,
        provider=resolved_provider,
        model=resolved_model,
    )
    session_id = session or service.create_session()
    console.print(f"[dim]AI session:[/] {session_id}")

    if prompt:
        result = service.send_message(session_id, prompt, EntryPoint.CLI)
        console.print(result.final_text)
        return

    console.print("[bold green]MitoFlow AI Chat[/] Type 'exit' to quit.")
    while True:
        user_text = console.input("[bold]you> [/]").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        if not user_text:
            continue
        result = service.send_message(session_id, user_text, EntryPoint.CLI)
        console.print(f"[bold green]ai>[/] {result.final_text}")
```

- [ ] **Step 4: Run CLI test**

Run:

```bash
pytest tests/test_ai_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Smoke-test the command manually**

Run:

```bash
MITOFLOW_AI_PROVIDER=fake mitoflow ai-chat --prompt "hello" --sessions-dir /tmp/mitoflow-ai-sessions --workspace .
```

Expected output includes `MitoFlow AI is configured with the fake provider`.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add src/mitoflow/cli.py tests/test_ai_cli.py
git commit -m "feat(ai): add ai chat cli entry"
```

---

### Task 5: FastAPI AI Endpoints

**Files:**
- Modify: `deploy/web/backend/main.py:32-42`
- Test: `tests/test_ai_fastapi.py`
- Modify: `pyproject.toml:33-41`

- [ ] **Step 1: Add web test dependencies**

Modify `pyproject.toml` optional dependencies:

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "fastapi>=0.104", "httpx>=0.25"]
ai = ["openai>=1.0", "anthropic>=0.40"]
web = ["fastapi>=0.104", "uvicorn>=0.24", "python-multipart", "streamlit>=1.28", "requests>=2.31"]
```

Keep existing optional dependency entries below these lines.

- [ ] **Step 2: Write failing FastAPI tests**

Create `tests/test_ai_fastapi.py`:

```python
"""Tests for FastAPI AI endpoints."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
WEB_BACKEND = ROOT / "deploy" / "web" / "backend"
if str(WEB_BACKEND) not in sys.path:
    sys.path.insert(0, str(WEB_BACKEND))

import main  # noqa: E402


def test_ai_tools_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("MITOFLOW_AI_PROVIDER", "fake")
    monkeypatch.setattr(main, "AI_SESSIONS_DIR", tmp_path / "sessions", raising=False)
    monkeypatch.setattr(main, "AI_WORKSPACE_DIR", tmp_path, raising=False)
    client = TestClient(main.app)

    response = client.get("/api/ai/tools")

    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["tools"]}
    assert "list_mitoflow_modules" in names


def test_ai_session_message_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("MITOFLOW_AI_PROVIDER", "fake")
    monkeypatch.setattr(main, "AI_SESSIONS_DIR", tmp_path / "sessions", raising=False)
    monkeypatch.setattr(main, "AI_WORKSPACE_DIR", tmp_path, raising=False)
    client = TestClient(main.app)

    session_response = client.post("/api/ai/sessions")
    session_id = session_response.json()["session_id"]
    message_response = client.post(
        f"/api/ai/sessions/{session_id}/messages",
        json={"message": "hello"},
    )

    assert message_response.status_code == 200
    assert "MitoFlow AI is configured with the fake provider" in message_response.json()["final_text"]
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
pytest tests/test_ai_fastapi.py -v
```

Expected: FAIL because `/api/ai/*` endpoints do not exist.

- [ ] **Step 4: Add API request and response models**

Modify `deploy/web/backend/main.py` after `TaskStatus`:

```python

class AISessionResponse(BaseModel):
    """AI session creation response."""
    session_id: str


class AIMessageRequest(BaseModel):
    """AI chat message request."""
    message: str
    provider: Optional[str] = None
    model: Optional[str] = None


class AIMessageResponse(BaseModel):
    """AI chat message response."""
    session_id: str
    final_text: str
    events: list[dict]
    tool_results: list[dict]
```

- [ ] **Step 5: Add AI config and service helper**

Modify `deploy/web/backend/main.py` after `tasks = {}`:

```python
AI_SESSIONS_DIR = Path(os.getenv("AI_SESSIONS_DIR", "/app/ai_sessions"))
AI_WORKSPACE_DIR = Path(os.getenv("AI_WORKSPACE_DIR", "/app"))
AI_SESSIONS_DIR.mkdir(exist_ok=True)


def build_ai_service(provider: Optional[str] = None, model: Optional[str] = None):
    """Build the shared AI service for API requests."""
    from mitoflow.ai.service import AIService, build_provider

    resolved_provider, resolved_model = build_provider(provider_name=provider, model=model)
    return AIService(
        session_root=AI_SESSIONS_DIR,
        workspace_root=AI_WORKSPACE_DIR,
        provider=resolved_provider,
        model=resolved_model,
    )
```

- [ ] **Step 6: Add AI endpoints**

Modify `deploy/web/backend/main.py` before `@app.get("/api/health")`:

```python

@app.get("/api/ai/health")
async def ai_health_check():
    """Health check for AI service."""
    return {"status": "healthy", "provider": os.getenv("MITOFLOW_AI_PROVIDER", "fake")}


@app.get("/api/ai/tools")
async def list_ai_tools():
    """List AI tools exposed to the API."""
    from mitoflow.ai.models import EntryPoint

    service = build_ai_service()
    return {"tools": service.list_tools(EntryPoint.API)}


@app.post("/api/ai/sessions", response_model=AISessionResponse)
async def create_ai_session():
    """Create an AI chat session."""
    service = build_ai_service()
    return AISessionResponse(session_id=service.create_session())


@app.get("/api/ai/sessions/{session_id}")
async def get_ai_session(session_id: str):
    """Get stored AI session messages and events."""
    service = build_ai_service()
    if not service.store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="AI session not found")
    return {
        "session_id": session_id,
        "messages": [m.model_dump(mode="json") for m in service.store.load_messages(session_id)],
        "events": [e.model_dump(mode="json") for e in service.store.load_events(session_id)],
    }


@app.post("/api/ai/sessions/{session_id}/messages", response_model=AIMessageResponse)
async def send_ai_message(session_id: str, request: AIMessageRequest):
    """Send a message to an AI session."""
    from mitoflow.ai.models import EntryPoint

    service = build_ai_service(provider=request.provider, model=request.model)
    if not service.store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="AI session not found")
    result = service.send_message(
        session_id=session_id,
        message=request.message,
        entry_point=EntryPoint.API,
    )
    return AIMessageResponse(
        session_id=session_id,
        final_text=result.final_text,
        events=[event.model_dump(mode="json") for event in result.events],
        tool_results=[tool.model_dump(mode="json") for tool in result.tool_results],
    )


@app.get("/api/ai/sessions/{session_id}/events")
async def get_ai_events(session_id: str):
    """List runtime events for an AI session."""
    service = build_ai_service()
    if not service.store.session_exists(session_id):
        raise HTTPException(status_code=404, detail="AI session not found")
    return {"events": [event.model_dump(mode="json") for event in service.store.load_events(session_id)]}
```

- [ ] **Step 7: Run FastAPI tests**

Run:

```bash
pytest tests/test_ai_fastapi.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 5**

Run:

```bash
git add pyproject.toml deploy/web/backend/main.py tests/test_ai_fastapi.py
git commit -m "feat(ai): add fastapi ai chat endpoints"
```

---

### Task 6: Streamlit AI Chat Page

**Files:**
- Modify: `deploy/web/frontend/app.py:43-87`
- Modify: `deploy/web/frontend/app.py:121-313`

- [ ] **Step 1: Add frontend AI API helpers**

Modify `deploy/web/frontend/app.py` after `download_results`:

```python

def create_ai_session():
    """Create an AI chat session."""
    response = requests.post(f"{API_URL}/api/ai/sessions", timeout=10)
    return response


def send_ai_message(session_id, message, provider=None, model=None):
    """Send a message to an AI session."""
    payload = {"message": message, "provider": provider or None, "model": model or None}
    response = requests.post(
        f"{API_URL}/api/ai/sessions/{session_id}/messages",
        json=payload,
        timeout=120,
    )
    return response


def get_ai_tools():
    """List available AI tools."""
    response = requests.get(f"{API_URL}/api/ai/tools", timeout=10)
    return response
```

- [ ] **Step 2: Change tabs to include AI Chat**

Modify line 122:

```python
tab1, tab2, tab3, tab4 = st.tabs(["New Analysis", "Task Status", "AI Chat", "Help"])
```

Keep existing `with tab1:` and `with tab2:` blocks unchanged.

- [ ] **Step 3: Insert AI Chat tab before Help**

Move the existing Help block from `with tab3:` to `with tab4:`. Add this new `with tab3:` block before it:

```python
with tab3:
    st.header("AI Chat")

    col1, col2 = st.columns([2, 1])
    with col2:
        provider = st.selectbox("Provider", ["fake", "openai", "anthropic"], index=0)
        model = st.text_input("Model", value="")
        if st.button("Show Available Tools", use_container_width=True):
            try:
                tools_response = get_ai_tools()
                if tools_response.status_code == 200:
                    tools = tools_response.json()["tools"]
                    st.json([{"name": tool["name"], "safety": tool["safety_level"]} for tool in tools])
                else:
                    st.error(tools_response.text)
            except Exception as e:
                st.error(f"Failed to load tools: {e}")

    with col1:
        if "ai_session_id" not in st.session_state:
            try:
                session_response = create_ai_session()
                if session_response.status_code == 200:
                    st.session_state["ai_session_id"] = session_response.json()["session_id"]
                    st.session_state["ai_messages"] = []
                else:
                    st.error(session_response.text)
            except Exception as e:
                st.error(f"Failed to create AI session: {e}")

        session_id = st.session_state.get("ai_session_id")
        if session_id:
            st.caption(f"Session: {session_id[:8]}")

            for message in st.session_state.get("ai_messages", []):
                with st.chat_message(message["role"]):
                    st.write(message["content"])

            user_prompt = st.chat_input("Ask MitoFlow AI about analyses, files, or workflows")
            if user_prompt:
                st.session_state["ai_messages"].append({"role": "user", "content": user_prompt})
                with st.chat_message("user"):
                    st.write(user_prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            response = send_ai_message(
                                session_id=session_id,
                                message=user_prompt,
                                provider=provider,
                                model=model.strip() or None,
                            )
                            if response.status_code == 200:
                                payload = response.json()
                                answer = payload["final_text"]
                                st.write(answer)
                                st.session_state["ai_messages"].append({"role": "assistant", "content": answer})
                                if payload.get("tool_results"):
                                    with st.expander("Tool Results"):
                                        st.json(payload["tool_results"])
                            else:
                                st.error(response.text)
                        except Exception as e:
                            st.error(f"AI request failed: {e}")
```

- [ ] **Step 4: Run syntax checks**

Run:

```bash
python -m py_compile deploy/web/frontend/app.py
```

Expected: no output and exit code 0.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add deploy/web/frontend/app.py
git commit -m "feat(ai): add streamlit ai chat tab"
```

---

### Task 7: Docker Configuration, Full Verification, and Documentation Link

**Files:**
- Modify: `deploy/docker/Dockerfile.web:45-55`
- Modify: `deploy/docker/docker-compose.yml:30-32`
- Modify: `README.md`

- [ ] **Step 1: Update Docker Python dependencies**

Modify `deploy/docker/Dockerfile.web` lines 46-55:

```dockerfile
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[ai,web]" && \
    pip install --no-cache-dir \
    celery \
    redis
```

- [ ] **Step 2: Pass AI environment variables in compose**

Modify the `api.environment` list in `deploy/docker/docker-compose.yml`:

```yaml
      - REDIS_URL=redis://redis:6379/0
      - MAX_WORKERS=2
      - MITOFLOW_AI_PROVIDER=${MITOFLOW_AI_PROVIDER:-fake}
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - OPENAI_BASE_URL=${OPENAI_BASE_URL:-}
      - OPENAI_MODEL=${OPENAI_MODEL:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-}
      - AI_SESSIONS_DIR=/app/ai_sessions
      - AI_WORKSPACE_DIR=/app
```

Add an `ai_sessions` volume to `api.volumes`:

```yaml
      - ai_sessions:/app/ai_sessions
```

Add the same AI provider environment variables to `frontend.environment` if the UI needs defaults:

```yaml
      - API_URL=http://api:8000
      - MITOFLOW_AI_PROVIDER=${MITOFLOW_AI_PROVIDER:-fake}
```

Add the new volume under `volumes`:

```yaml
  ai_sessions:
```

- [ ] **Step 3: Add README AI section**

Modify `README.md` after the Quick Start section:

````markdown
## AI Chat Preview

MitoFlow includes an experimental AI orchestration layer for conversational analysis.

Local fake-provider smoke test:

```bash
MITOFLOW_AI_PROVIDER=fake mitoflow ai-chat --prompt "What can MitoFlow do?"
```

OpenAI-compatible provider:

```bash
export MITOFLOW_AI_PROVIDER=openai
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-5.2
mitoflow ai-chat
```

Anthropic Claude provider:

```bash
export MITOFLOW_AI_PROVIDER=anthropic
export ANTHROPIC_API_KEY=...
export ANTHROPIC_MODEL=claude-opus-4-1-20250805
mitoflow ai-chat
```

The AI layer uses an allowlisted tool registry. It does not execute arbitrary shell commands from model output.
````

- [ ] **Step 4: Run targeted test suite**

Run:

```bash
pytest tests/test_ai_models.py tests/test_ai_tools.py tests/test_ai_sessions.py tests/test_ai_providers.py tests/test_ai_runtime.py tests/test_ai_service.py tests/test_ai_cli.py tests/test_ai_fastapi.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run:

```bash
pytest -v
```

Expected: PASS. If external bioinformatics tools are unavailable and existing tests skip or fail for environmental reasons, record exact failures and rerun the AI-specific suite to isolate this change.

- [ ] **Step 6: Run CLI smoke test**

Run:

```bash
MITOFLOW_AI_PROVIDER=fake mitoflow ai-chat --prompt "List available modules" --sessions-dir /tmp/mitoflow-ai-sessions --workspace .
```

Expected: output includes a fake-provider response. After provider scripting is extended, output can include tool results from `list_mitoflow_modules`.

- [ ] **Step 7: Run API smoke test when web dependencies are installed**

Run backend:

```bash
MITOFLOW_AI_PROVIDER=fake uvicorn deploy.web.backend.main:app --host 127.0.0.1 --port 8000
```

In another shell:

```bash
curl -s http://127.0.0.1:8000/api/ai/tools
```

Expected: JSON response includes `list_mitoflow_modules`.

- [ ] **Step 8: Commit Task 7**

Run:

```bash
git add deploy/docker/Dockerfile.web deploy/docker/docker-compose.yml README.md
git commit -m "docs(ai): document ai chat deployment configuration"
```

---

## Final Verification

Run:

```bash
git status --short
pytest tests/test_ai_models.py tests/test_ai_tools.py tests/test_ai_sessions.py tests/test_ai_providers.py tests/test_ai_runtime.py tests/test_ai_service.py tests/test_ai_cli.py tests/test_ai_fastapi.py -v
python -m py_compile src/mitoflow/cli.py deploy/web/backend/main.py deploy/web/frontend/app.py
```

Expected:

- `git status --short` shows only unrelated pre-existing user changes or no changes after commits.
- AI test suite passes.
- Python compile checks pass.

## Execution Notes

- Keep live OpenAI and Anthropic API calls out of tests. Use `FakeProvider` and mocked clients.
- Do not expose API keys to Streamlit; provider keys stay in the backend environment.
- Keep arbitrary code execution out of the tool registry.
- Keep the first phase focused on the AI kernel and thin entry points. Chloroplast, mitochondrial assembly, and pan-organelle capabilities are added as later registered tool packages.
