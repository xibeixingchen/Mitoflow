"""DeepAgents-powered AI service — real create_deep_agent() integration.

Supports:
  - DeepAgents 0.5.x with LangGraph state machine
  - OpenAI-compatible LLMs (DeepSeek, GLM, Kimi, Qwen, etc.)
  - Anthropic-compatible LLMs (Kimi Code, Claude)
  - Sub-agent delegation via DeepAgents' built-in task tool
  - Planning via write_todos
  - All 21 MitoFlow tools
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import EntryPoint


def create_deep_mitoflow_agent(
    provider: str = "openai",
    model: str = "gpt-4o",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    tools: Optional[List[Any]] = None,
    system_prompt: Optional[str] = None,
) -> Any:
    """Create a DeepAgents-powered MitoFlow agent.

    Args:
        provider: "openai" or "anthropic"
        model: Model ID string
        api_key: API key (falls back to env var)
        base_url: Custom base URL for compatible APIs
        tools: List of LangChain tools
        system_prompt: System prompt override
    """
    from deepagents import create_deep_agent

    # Use LangChain's init_chat_model for provider-agnostic model creation
    # Format: "provider:model" — LangChain auto-detects ChatOpenAI/ChatAnthropic
    if provider == "anthropic":
        # Anthropic protocol (Kimi Code, Claude) — use ChatAnthropic
        from langchain_anthropic import ChatAnthropic
        kwargs: Dict[str, Any] = {"model": model}
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
        if resolved_key:
            kwargs["api_key"] = resolved_key
        if base_url:
            kwargs["base_url"] = base_url
        llm = ChatAnthropic(**kwargs)
    else:
        # OpenAI protocol (DeepSeek, GLM, Kimi, Qwen, OpenAI, etc.) — use ChatOpenAI
        from langchain_openai import ChatOpenAI
        kwargs = {"model": model}
        resolved_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("ZHIPU_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        if resolved_key:
            kwargs["api_key"] = resolved_key
        if base_url:
            kwargs["base_url"] = base_url
        llm = ChatOpenAI(**kwargs)

    return create_deep_agent(
        model=llm,
        tools=tools or [],
        system_prompt=system_prompt or _DEFAULT_SYSTEM_PROMPT,
    )


def mitoflow_tools_to_langchain() -> List[Any]:
    """Convert MitoFlow's 21 tools to LangChain StructuredTool format."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from .service import build_default_registry
    from .tools import ToolContext

    registry = build_default_registry()
    lc_tools = []

    for tool_def in registry.definitions(EntryPoint.CLI):
        # Dynamically create a Pydantic model for the tool's input schema
        tool_name = tool_def.name
        tool_desc = tool_def.description
        params = tool_def.parameters.get("properties", {})
        required = tool_def.parameters.get("required", [])

        # Build Pydantic field definitions from JSON Schema
        annotations: Dict[str, Any] = {}
        namespace: Dict[str, Any] = {"__doc__": tool_desc}
        for param_name, param_info in params.items():
            param_type = _json_type_to_python(param_info.get("type", "string"))
            param_desc = param_info.get("description", "")
            is_required = param_name in required
            annotations[param_name] = param_type
            if is_required:
                namespace[param_name] = Field(description=param_desc)
            else:
                namespace[param_name] = Field(default=None, description=param_desc)

        # Create the schema model
        SchemaModel = type(
            f"{tool_name}_schema",
            (BaseModel,),
            {"__annotations__": annotations, **namespace},
        )

        # Get the executor function from registry
        executor = registry._executors.get(tool_name)

        if executor:
            # Closure-safe executor factory
            def _make_executor(exec_fn):
                def _run(**kwargs):
                    result = exec_fn(kwargs, ToolContext(
                        session_id="deepagent",
                        workspace_root=Path.cwd(),
                        output_root=Path.cwd() / ".mitoflow_output",
                        entry_point=EntryPoint.CLI,
                    ))
                    return result.get("content", str(result))
                return _run

            lc_tools.append(StructuredTool(
                name=tool_name,
                description=tool_desc,
                args_schema=SchemaModel,
                func=_make_executor(executor),
            ))

    return lc_tools


def _json_type_to_python(json_type: str) -> type:
    mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return mapping.get(json_type, str)


_DEFAULT_SYSTEM_PROMPT = """\
You are MitoFlow AI, a plant mitochondrial genomics assistant powered by DeepAgents.

## Your Capabilities
- Answer questions about plant mitochondrial genes, genomes, and evolution
- Guide users through analysis workflows: assembly, annotation, QC, ERC, CMS detection
- Provide literature references (DOI/PMID) for factual claims
- Delegate complex multi-step tasks to sub-agents

## Domain Knowledge
- Plant mitochondrial genomes: 200 kb to >10 Mb, variable gene order
- Core protein-coding genes: ~24 conserved across land plants
- Respiratory chain complexes I-V encoded by mitochondrial and nuclear genes
- RNA editing: extensive C-to-U editing (400-1500 sites per genome)
- Trans-splicing: nad1, nad2, nad3, nad4, nad5, nad6, rps10
- CMS: cytoplasmic male sterility caused by chimeric mitochondrial ORFs

## Guidelines
1. Always cite references (authors, year, DOI) when making factual claims
2. Use the tools to look up specific gene information, not from memory
3. For complex analysis tasks, use delegate_task to spawn sub-agents
4. Structure responses clearly with headings and tables
5. Answer in the same language as the user's query
"""
