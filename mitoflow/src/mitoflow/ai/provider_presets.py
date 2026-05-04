"""Pre-configured LLM provider presets for Chinese and international models.

Inspired by STELLA's OpenRouter approach — most LLMs support OpenAI Chat
Completions protocol. Provider presets map provider names to base URLs and
default models, so users can select by name instead of typing URLs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ProviderPreset:
    name: str          # Display name
    key: str           # Internal key
    protocol: str      # "openai" or "anthropic"
    base_url: str      # API endpoint
    models: List[str]  # Available model IDs
    env_key: str = ""  # Env var for API key (auto-detected)
    description: str = ""


# Provider presets — all tested and working
PROVIDER_PRESETS: List[ProviderPreset] = [
    ProviderPreset(
        name="DeepSeek",
        key="deepseek",
        protocol="openai",
        base_url="https://api.deepseek.com/v1",
        models=["deepseek-chat", "deepseek-reasoner"],
        env_key="DEEPSEEK_API_KEY",
        description="DeepSeek — cost-effective, strong coding & reasoning",
    ),
    ProviderPreset(
        name="GLM (ZhipuAI)",
        key="zhipu",
        protocol="openai",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        models=["glm-4-plus", "glm-4-flash", "glm-4-long"],
        env_key="ZHIPU_API_KEY",
        description="ZhipuAI GLM-4 series — strong Chinese language support",
    ),
    ProviderPreset(
        name="Kimi (Moonshot)",
        key="moonshot",
        protocol="openai",
        base_url="https://api.moonshot.cn/v1",
        models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        env_key="MOONSHOT_API_KEY",
        description="Moonshot Kimi — long context, Chinese-optimized",
    ),
    ProviderPreset(
        name="Kimi Code",
        key="kimicode",
        protocol="anthropic",
        base_url="https://api.kimi.com/coding/",
        models=["K2.6"],
        env_key="KIMICODE_AUTH_TOKEN",
        description="Kimi Coding — Anthropic protocol, code generation",
    ),
    ProviderPreset(
        name="Qwen (Tongyi)",
        key="qwen",
        protocol="openai",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=["qwen-plus", "qwen-max", "qwen-turbo", "qwen-long"],
        env_key="DASHSCOPE_API_KEY",
        description="Alibaba Tongyi Qianwen — versatile, strong multilingual",
    ),
    ProviderPreset(
        name="Baichuan",
        key="baichuan",
        protocol="openai",
        base_url="https://api.baichuan-ai.com/v1",
        models=["Baichuan4", "Baichuan3-Turbo"],
        env_key="BAICHUAN_API_KEY",
        description="Baichuan — strong Chinese reasoning",
    ),
    ProviderPreset(
        name="MiniMax",
        key="minimax",
        protocol="openai",
        base_url="https://api.minimax.chat/v1",
        models=["abab6.5s-chat", "abab7-chat"],
        env_key="MINIMAX_API_KEY",
        description="MiniMax — fast, Chinese-focused",
    ),
    ProviderPreset(
        name="Yi (01.AI)",
        key="yi",
        protocol="openai",
        base_url="https://api.lingyiwanwu.com/v1",
        models=["yi-large", "yi-medium", "yi-vision"],
        env_key="YI_API_KEY",
        description="01.AI Yi series — large context window",
    ),
    ProviderPreset(
        name="Claude (Anthropic)",
        key="claude",
        protocol="anthropic",
        base_url="",
        models=["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"],
        env_key="ANTHROPIC_API_KEY",
        description="Anthropic Claude — strongest reasoning, native Anthropic protocol",
    ),
    ProviderPreset(
        name="OpenAI",
        key="openai",
        protocol="openai",
        base_url="https://api.openai.com/v1",
        models=["gpt-4o", "gpt-4o-mini", "o3-mini", "o1"],
        env_key="OPENAI_API_KEY",
        description="OpenAI GPT series — broad capability",
    ),
    ProviderPreset(
        name="OpenRouter",
        key="openrouter",
        protocol="openai",
        base_url="https://openrouter.ai/api/v1",
        models=["openai/gpt-4o", "anthropic/claude-sonnet-4", "google/gemini-2.5-pro", "deepseek/deepseek-chat"],
        env_key="OPENROUTER_API_KEY",
        description="OpenRouter — unified gateway to 200+ models (like STELLA)",
    ),
    ProviderPreset(
        name="Ollama (Local)",
        key="ollama",
        protocol="openai",
        base_url="http://localhost:11434/v1",
        models=["llama3", "qwen2.5", "deepseek-r1"],
        env_key="OLLAMA_API_KEY",
        description="Local models via Ollama — fully offline, no API key needed",
    ),
    ProviderPreset(
        name="vLLM / Custom",
        key="custom",
        protocol="openai",
        base_url="",
        models=[""],
        env_key="",
        description="Any OpenAI-compatible endpoint — self-hosted or custom",
    ),
]


def find_preset(key: str) -> Optional[ProviderPreset]:
    """Find provider preset by key."""
    for p in PROVIDER_PRESETS:
        if p.key == key:
            return p
    return None


def get_preset_list() -> list:
    """List all presets for UI."""
    return [
        {"key": p.key, "name": p.name, "protocol": p.protocol, "description": p.description}
        for p in PROVIDER_PRESETS
    ]
