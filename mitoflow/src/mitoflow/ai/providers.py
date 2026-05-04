"""Provider adapters for OpenAI-compatible and Anthropic Claude APIs."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .models import AIMessage, ProviderRequest, ProviderResponse, ToolCall, ToolDefinition


class FakeProvider:
    """Scripted provider for tests and offline development."""

    def __init__(self, responses: List[Dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.requests: List[ProviderRequest] = []

    def create(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if not self.responses:
            payload: Dict[str, Any] = {"content": "No scripted response available."}
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
        base_url: Optional[str] = None,
        client: Any = None,
    ) -> None:
        self.model = model
        if client is not None:
            self.client = client
        else:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("Install the 'openai' package to use the OpenAI provider") from exc
            kwargs: Dict[str, Any] = {"api_key": api_key}
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

    def format_messages(self, messages: List[AIMessage]) -> List[Dict[str, Any]]:
        formatted: List[Dict[str, Any]] = []
        for message in messages:
            item: Dict[str, Any] = {"role": message.role, "content": message.content or ""}
            if message.name:
                item["name"] = message.name
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            # Include tool_calls in assistant messages for OpenAI protocol
            if message.role == "assistant" and message.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in message.tool_calls
                ]
            formatted.append(item)
        return formatted

    def format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
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
        calls: List[ToolCall] = []
        for call in getattr(message, "tool_calls", None) or []:
            arguments_raw = call.function.arguments or "{}"
            try:
                arguments = json.loads(arguments_raw)
            except json.JSONDecodeError:
                arguments = {"_raw": arguments_raw}
            calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))

        usage = getattr(raw, "usage", None)
        usage_data: Dict[str, Any] = {}
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
    """Adapter for Anthropic Messages API and compatible services (Kimi, DeepSeek, etc.)."""

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None, client: Any = None) -> None:
        self.model = model
        if client is not None:
            self.client = client
        else:
            try:
                import anthropic
            except ImportError as exc:
                raise RuntimeError("Install the 'anthropic' package to use the Anthropic provider") from exc
            kwargs: Dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = anthropic.Anthropic(**kwargs)

    def create(self, request: ProviderRequest) -> ProviderResponse:
        system, messages = self.format_messages(request.messages)
        kwargs: Dict[str, Any] = {
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

    def format_messages(self, messages: List[AIMessage]) -> tuple:
        system_parts: List[str] = []
        formatted: List[Dict[str, Any]] = []
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
            elif message.role == "assistant" and message.tool_calls:
                # Assistant message with tool_use blocks — must include them in content
                content_blocks: List[Dict[str, Any]] = []
                if message.content:
                    content_blocks.append({"type": "text", "text": message.content})
                for tc in message.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                formatted.append({"role": "assistant", "content": content_blocks})
            else:
                formatted.append({"role": message.role, "content": message.content})
        return ("\n".join(system_parts) if system_parts else None), formatted

    def format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    def parse_response(self, raw: Any) -> ProviderResponse:
        text_parts: List[str] = []
        calls: List[ToolCall] = []
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
        usage_data: Dict[str, Any] = {}
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
