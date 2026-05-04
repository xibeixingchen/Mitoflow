"""Manager runtime loop for MitoFlow AI."""

from __future__ import annotations

from typing import Any, Dict, List

from .models import AIMessage, ProviderRequest, RuntimeEvent, RuntimeResult, ToolResult
from .prompts import MANAGER_SYSTEM_PROMPT
try:
    from .domain_prompts import MANAGER_SYSTEM_PROMPT_WITH_KNOWLEDGE
    _DEFAULT_PROMPT = MANAGER_SYSTEM_PROMPT_WITH_KNOWLEDGE
except ImportError:
    _DEFAULT_PROMPT = MANAGER_SYSTEM_PROMPT
from .sessions import LocalSessionStore
from .tools import ToolContext, ToolRegistry


class AgentRuntime:
    """Synchronous manager-agent loop for one chat turn."""

    def __init__(
        self,
        provider: Any,
        registry: ToolRegistry,
        store: LocalSessionStore,
        model: str,
        max_turns: int = 12,
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

        events: List[RuntimeEvent] = []
        tool_results: List[ToolResult] = []
        usage: Dict[str, int] = {}

        for turn_index in range(self.max_turns):
            messages = self._messages_with_system(session_id)
            response = self.provider.create(
                ProviderRequest(
                    model=self.model,
                    messages=messages,
                    tools=self.registry.definitions(context.entry_point),
                )
            )
            # Store tool_calls in the assistant message for Anthropic protocol
            if response.tool_calls:
                response.message.tool_calls = response.tool_calls
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

    def _messages_with_system(self, session_id: str) -> List[AIMessage]:
        messages = self.store.load_messages(session_id)
        if messages and messages[0].role == "system":
            return messages
        return [AIMessage(role="system", content=_DEFAULT_PROMPT)] + messages

    def _merge_usage(self, target: Dict[str, int], source: Dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, int):
                target[key] = target.get(key, 0) + value
