"""Application-facing AI service for CLI, API, and Web entry points."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .mitoflow_tools import register_mitoflow_tools
from .models import EntryPoint, RuntimeResult
from .providers import AnthropicAdapter, FakeProvider, OpenAIChatAdapter
from .runtime import AgentRuntime
from .sessions import LocalSessionStore
from .tools import ToolContext, ToolRegistry


def build_default_registry() -> ToolRegistry:
    """Build the default allowlisted registry."""
    registry = ToolRegistry()
    register_mitoflow_tools(registry)
    return registry


def build_provider(provider_name: Optional[str] = None, model: Optional[str] = None,
                   api_key: Optional[str] = None, base_url: Optional[str] = None) -> Tuple[Any, str]:
    """Build a provider from environment or explicit parameters."""
    provider = (provider_name or os.getenv("MITOFLOW_AI_PROVIDER") or "fake").lower()
    if provider == "fake":
        return FakeProvider(responses=[{"content": "MitoFlow AI is configured with the fake provider."}]), model or "fake"
    if provider == "openai":
        selected_model = model or os.getenv("OPENAI_MODEL") or "gpt-4o"
        # Try multiple env var names for API key compatibility
        resolved_key = (api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
                        or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY"))
        if not resolved_key:
            raise ValueError("Set OPENAI_API_KEY / DEEPSEEK_API_KEY or provide api_key")
        return (
            OpenAIChatAdapter(
                api_key=resolved_key,
                model=selected_model,
                base_url=base_url or os.getenv("OPENAI_BASE_URL"),
            ),
            selected_model,
        )
    if provider == "anthropic":
        selected_model = model or os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514"
        resolved_key = (api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
                        or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY"))
        if not resolved_key:
            raise ValueError("Set ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN or provide api_key")
        return AnthropicAdapter(
            api_key=resolved_key, model=selected_model,
            base_url=base_url or os.getenv("ANTHROPIC_BASE_URL"),
        ), selected_model
    raise ValueError(f"Unsupported AI provider: {provider}")


class AIService:
    """Shared service used by CLI, API, and Web layers."""

    def __init__(
        self,
        session_root: Path | str,
        workspace_root: Path | str,
        registry: Optional[ToolRegistry] = None,
        provider: Any = None,
        model: Optional[str] = None,
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

    def list_tools(self, entry_point: EntryPoint) -> List[Dict[str, Any]]:
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
