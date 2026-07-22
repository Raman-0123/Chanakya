"""Concrete LLM provider adapters.

Mistral, Groq, NVIDIA NIM, OpenRouter, and DeepSeek all expose OpenAI-compatible
Chat Completions endpoints, so they share a single adapter parameterised by
base URL / key / model. Google Gemini has its own SDK and gets a dedicated
adapter. All are constructed lazily and never raise at import time.
"""

from __future__ import annotations

import time
from typing import Literal

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import (
    BaseLLMProvider,
    LLMMessage,
    LLMProviderError,
    LLMResponse,
)

log = get_logger("llm.providers")


# ---------------------------------------------------------------------------
#  OpenAI-compatible providers (Mistral / Groq / NVIDIA / OpenRouter / DeepSeek)
# ---------------------------------------------------------------------------
class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(self, name: str, api_key: str, base_url: str, model: str):
        self.name = name
        self.model = model
        self._api_key = api_key
        self._base_url = base_url
        self._client = None  # lazy

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self._api_key, base_url=self._base_url, timeout=45.0
            )
        return self._client

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResponse:
        if not self.is_configured:
            raise LLMProviderError(self.name, "no API key configured")

        client = self._get_client()
        kwargs: dict = {
            "model": self.model,
            "messages": [m.as_openai() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        try:
            resp = await client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalise to router-catchable error
            raise LLMProviderError(self.name, str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = resp.choices[0]
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            content=choice.message.content or "",
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            tokens_in=getattr(usage, "prompt_tokens", None) if usage else None,
            tokens_out=getattr(usage, "completion_tokens", None) if usage else None,
            finish_reason=choice.finish_reason,
        )


# ---------------------------------------------------------------------------
#  Google Gemini
# ---------------------------------------------------------------------------
class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        self.name = "gemini"
        self.model = model
        self._api_key = api_key
        self._configured_sdk = False

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _ensure_sdk(self):
        if not self._configured_sdk:
            import google.generativeai as genai

            genai.configure(api_key=self._api_key)
            self._genai = genai
            self._configured_sdk = True
        return self._genai

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResponse:
        if not self.is_configured:
            raise LLMProviderError(self.name, "no API key configured")

        genai = self._ensure_sdk()

        # Gemini keeps system instruction separate; concatenate user/assistant turns.
        system_parts = [m.content for m in messages if m.role.value == "system"]
        convo = [
            {"role": "user" if m.role.value != "assistant" else "model",
             "parts": [m.content]}
            for m in messages
            if m.role.value != "system"
        ]

        gen_config: dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if response_format == "json":
            gen_config["response_mime_type"] = "application/json"

        model = genai.GenerativeModel(
            self.model,
            system_instruction="\n\n".join(system_parts) or None,
            generation_config=gen_config,
        )

        start = time.perf_counter()
        try:
            resp = await model.generate_content_async(convo)
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(self.name, str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        return LLMResponse(
            content=(resp.text or ""),
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
        )


# ---------------------------------------------------------------------------
#  Anthropic (Claude) — official SDK, Messages API
# ---------------------------------------------------------------------------
class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        self.name = "anthropic"
        self.model = model
        self._api_key = api_key
        self._client = None  # lazy

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key, timeout=45.0)
        return self._client

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResponse:
        if not self.is_configured:
            raise LLMProviderError(self.name, "no API key configured")

        client = self._get_client()
        # Anthropic keeps the system prompt separate; messages are user/assistant only.
        system = "\n\n".join(m.content for m in messages if m.role.value == "system")
        convo = [
            {"role": "assistant" if m.role.value == "assistant" else "user",
             "content": m.content}
            for m in messages if m.role.value != "system"
        ] or [{"role": "user", "content": "Proceed."}]

        # Note: current Claude models (Opus 4.8/4.7, Sonnet 5) reject `temperature`,
        # so we steer via the prompt instead of passing sampling params.
        kwargs: dict = {"model": self.model, "max_tokens": max_tokens, "messages": convo}
        if system:
            kwargs["system"] = system

        start = time.perf_counter()
        try:
            resp = await client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalise to router-catchable error
            raise LLMProviderError(self.name, str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        text = "".join(
            getattr(block, "text", "") for block in resp.content
            if getattr(block, "type", "") == "text"
        )
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            content=text,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            tokens_in=getattr(usage, "input_tokens", None) if usage else None,
            tokens_out=getattr(usage, "output_tokens", None) if usage else None,
            finish_reason=getattr(resp, "stop_reason", None),
        )


# ---------------------------------------------------------------------------
#  Registry
# ---------------------------------------------------------------------------
_BASE_URLS = {
    "mistral": "https://api.mistral.ai/v1",
    "groq": "https://api.groq.com/openai/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
}


def build_provider(name: str) -> BaseLLMProvider | None:
    """Instantiate a provider adapter by name, or None if unknown."""
    if name == "anthropic":
        return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
    if name == "gemini":
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    if name in _BASE_URLS:
        key = getattr(settings, f"{name}_api_key")
        model = getattr(settings, f"{name}_model")
        return OpenAICompatibleProvider(name, key, _BASE_URLS[name], model)
    return None
