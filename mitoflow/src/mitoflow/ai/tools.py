"""Tool registry and execution safety for MitoFlow AI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Union

from pydantic import BaseModel

from .models import EntryPoint, ToolCall, ToolDefinition, ToolResult

ToolExecutor = Callable[[Dict[str, Any], "ToolContext"], Union[Dict[str, Any], ToolResult]]


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
