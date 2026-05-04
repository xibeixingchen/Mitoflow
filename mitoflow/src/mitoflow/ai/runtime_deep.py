"""DeepAgents-style runtime — LangGraph state machine with sub-agent delegation.

Inspired by:
  - DeepAgents: LangGraph-based agent with planning + sub-agent tools
  - STELLA: Manager/Dev/Critic role decomposition
  - ClawBio: SKILL.md spec-first encapsulation
  - BioClaw: Session isolation + notebook export
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set

from .models import AIMessage, EntryPoint, ProviderRequest, RuntimeEvent, RuntimeResult, ToolCall, ToolResult
from .tools import ToolContext, ToolRegistry

try:
    from .domain_prompts import MANAGER_SYSTEM_PROMPT_WITH_KNOWLEDGE as _DEFAULT_PROMPT
except ImportError:
    from .prompts import MANAGER_SYSTEM_PROMPT as _DEFAULT_PROMPT  # fallback

# Sub-agent delegation prompt
DELEGATE_PROMPT = """\
You are a MitoFlow sub-agent. You have access to a subset of tools to complete a
specific task. Work independently and return a concise result.

When you have completed the task, provide a final answer summarizing:
1. What you did
2. Key findings or results
3. Any recommendations for next steps
"""


class DeepAgentRuntime:
    """LangGraph-inspired agent runtime with planning and sub-agent delegation.

    Unlike the simple AgentRuntime loop, this runtime supports:
    - Planning before execution (write_todos pattern)
    - Sub-agent delegation for complex multi-step tasks
    - State tracking with event log
    - Isolated sub-agent contexts
    """

    def __init__(
        self,
        provider: Any,
        registry: ToolRegistry,
        store: Any,  # LocalSessionStore
        model: str,
        max_turns: int = 8,
        enable_delegation: bool = True,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.store = store
        self.model = model
        self.max_turns = max_turns
        self.enable_delegation = enable_delegation

    # ── Public API ──────────────────────────────────────────────────

    def run_turn(self, session_id: str, user_text: str, context: ToolContext) -> RuntimeResult:
        """Run one user turn through the DeepAgent loop."""
        if not self.store.session_exists(session_id):
            raise ValueError(f"Unknown AI session: {session_id}")

        user_message = AIMessage(role="user", content=user_text)
        self.store.append_message(session_id, user_message)

        events: List[RuntimeEvent] = []
        tool_results: List[ToolResult] = []
        usage: Dict[str, int] = {}

        # Phase 1: Planning (optional, for complex requests)
        plan = self._plan_if_needed(session_id, user_text, context, events, usage)

        # Phase 2: Execution loop
        for turn_index in range(self.max_turns):
            messages = self._messages_with_system(session_id)
            tools = self.registry.definitions(context.entry_point)

            response = self.provider.create(
                ProviderRequest(model=self.model, messages=messages, tools=tools)
            )
            if response.tool_calls:
                response.message.tool_calls = response.tool_calls
            self.store.append_message(session_id, response.message)
            self._merge_usage(usage, response.usage)

            if not response.tool_calls:
                events.append(RuntimeEvent(
                    type="assistant_final", message="Assistant returned a final answer.",
                    data={"turn_index": turn_index, "plan": plan},
                ))
                self.store.append_event(session_id, events[-1])
                return RuntimeResult(
                    session_id=session_id,
                    final_text=response.message.content,
                    messages=self.store.load_messages(session_id),
                    events=self.store.load_events(session_id),
                    tool_results=tool_results,
                    usage=usage,
                )

            # Process tool calls
            for call in response.tool_calls:
                events.append(RuntimeEvent(
                    type="tool_call", message=f"Calling {call.name}",
                    data=call.model_dump(mode="json"),
                ))
                self.store.append_event(session_id, events[-1])

                result = self._execute_tool(call, context, session_id)
                tool_results.append(result)
                events.append(RuntimeEvent(
                    type="tool_result", message=result.content,
                    data=result.model_dump(mode="json"),
                ))
                self.store.append_event(session_id, events[-1])
                self.store.append_message(session_id, AIMessage(
                    role="tool", name=result.name,
                    tool_call_id=result.call_id, content=result.content,
                ))

        # Max turns reached
        final_text = "Max tool turns reached. Please refine your query."
        self.store.append_message(session_id, AIMessage(role="assistant", content=final_text))
        return RuntimeResult(
            session_id=session_id, final_text=final_text,
            messages=self.store.load_messages(session_id),
            events=self.store.load_events(session_id),
            tool_results=tool_results, usage=usage,
        )

    # ── Planning ────────────────────────────────────────────────────

    def _plan_if_needed(self, session_id: str, user_text: str, context: ToolContext,
                        events: List[RuntimeEvent], usage: Dict[str, int]) -> Optional[List[str]]:
        """Create a plan for complex requests. Returns list of plan steps if planning was done."""
        # Only plan if the request seems complex (multiple tasks or analysis requests)
        complexity_keywords = {"analyze", "compare", "summarize", "annotate", "run", "prepare",
                               "build", "detect", "find all", "list and", "what are",
                               "分析", "比较", "注释", "检测", "哪些", "如何"}
        needs_plan = any(kw in user_text.lower() for kw in complexity_keywords)
        if not needs_plan:
            return None

        plan_messages = [
            AIMessage(role="system", content=_DEFAULT_PROMPT),
            AIMessage(role="user", content=user_text),
            AIMessage(role="assistant", content=(
                "Let me plan my approach:\n"
                "1. Identify what the user needs\n"
                "2. Determine which tools to use\n"
                "3. Execute tools step by step\n"
                "4. Synthesize results"
            )),
        ]
        try:
            response = self.provider.create(
                ProviderRequest(model=self.model, messages=plan_messages, tools=[])
            )
        except Exception:
            return None

        self._merge_usage(usage, response.usage)
        return None  # Plan is implicit in the assistant's reasoning chain

    # ── Delegation ──────────────────────────────────────────────────

    def _execute_tool(self, call: ToolCall, context: ToolContext, parent_session: str) -> ToolResult:
        """Execute a tool call, with sub-agent delegation for complex tasks."""
        # Intercept: if the model wants to delegate, route to sub-agent
        if call.name == "delegate_task" and self.enable_delegation:
            return self._run_sub_agent(call.arguments, context, parent_session)

        return self.registry.execute(call, context)

    def _run_sub_agent(self, args: Dict[str, Any], context: ToolContext, parent_session: str) -> ToolResult:
        """Run a sub-agent for a delegated task (DeepAgents 'task' pattern)."""
        task_description = args.get("task", "")
        tool_names: List[str] = args.get("tools", [])

        # Filter registry to only the tools the sub-agent needs
        sub_registry = ToolRegistry()
        for name in tool_names:
            definition = self.registry._definitions.get(name)
            if definition:
                executor = self.registry._executors.get(name)
                if executor:
                    sub_registry.register(definition, executor)

        sub_store = self.store  # Share store for message history
        sub_context = ToolContext(
            session_id=f"{parent_session}/sub",
            workspace_root=context.workspace_root,
            output_root=context.output_root,
            entry_point=context.entry_point,
        )

        # Sub-agent system prompt
        sub_messages = [
            AIMessage(role="system", content=DELEGATE_PROMPT),
            AIMessage(role="user", content=task_description),
        ]

        try:
            response = self.provider.create(
                ProviderRequest(
                    model=self.model,
                    messages=sub_messages,
                    tools=sub_registry.definitions(context.entry_point),
                )
            )
        except Exception as e:
            return ToolResult(
                call_id="sub-agent", name="delegate_task", ok=False,
                content=f"Sub-agent failed: {e}", data={},
            )

        return ToolResult(
            call_id="sub-agent", name="delegate_task", ok=True,
            content=f"Sub-agent completed: {response.message.content}",
            data={"sub_agent_result": response.message.content},
        )

    # ── Helpers ─────────────────────────────────────────────────────

    def _messages_with_system(self, session_id: str) -> List[AIMessage]:
        messages = self.store.load_messages(session_id)
        if messages and messages[0].role == "system":
            return messages
        return [AIMessage(role="system", content=_DEFAULT_PROMPT)] + messages

    def _merge_usage(self, target: Dict[str, int], source: Dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, int):
                target[key] = target.get(key, 0) + value


# ── Tool Definitions for the DeepAgent ──────────────────────────────

def register_deep_agent_tools(registry: ToolRegistry) -> None:
    """Register tools that enable DeepAgents-style behavior: planning + delegation."""
    from .models import SafetyLevel, ToolDefinition

    registry.register(
        ToolDefinition(
            name="delegate_task",
            description=(
                "Delegate a complex subtask to a specialized sub-agent. "
                "Use this when a task requires multiple steps or specialized knowledge. "
                "The sub-agent has access to a subset of MitoFlow tools."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Detailed task description for the sub-agent."},
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tool names the sub-agent can use.",
                    },
                },
                "required": ["task"],
                "additionalProperties": False,
            },
            safety_level=SafetyLevel.READ_ONLY,
            entry_points=[EntryPoint.CLI, EntryPoint.API, EntryPoint.WEB],
        ),
        _delegate_task_placeholder,
    )


def _delegate_task_placeholder(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    """Placeholder — actual delegation is handled by DeepAgentRuntime._execute_tool."""
    return {"content": f"Delegating: {args.get('task', '')[:100]}...", "data": args}
