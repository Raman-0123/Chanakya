"""Multi-provider LLM router with ordered fallback.

The router asks each configured provider in turn (primary first). If a provider
is unconfigured, rate-limited, or errors, it moves to the next one. This is the
resilience layer that keeps the six-agent council alive across free-tier limits.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider, LLMMessage, LLMProviderError, LLMResponse
from app.llm.providers import build_provider

log = get_logger("llm.router")


class NoProviderAvailableError(RuntimeError):
    """No configured provider could satisfy the request."""


class LLMRouter:
    def __init__(self, provider_order: list[str] | None = None):
        order = provider_order or settings.configured_llm_providers
        self._providers: list[BaseLLMProvider] = []
        for name in order:
            provider = build_provider(name)
            if provider and provider.is_configured:
                self._providers.append(provider)

    @property
    def available(self) -> bool:
        return len(self._providers) > 0

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResponse:
        if not self._providers:
            raise NoProviderAvailableError(
                "No LLM provider is configured. Set at least one *_API_KEY in .env."
            )

        errors: list[str] = []
        for provider in self._providers:
            try:
                resp = await provider.complete(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
                if len(errors) > 0:
                    log.info(
                        "llm.fallback_success",
                        provider=provider.name,
                        skipped=errors,
                    )
                return resp
            except LLMProviderError as exc:
                errors.append(provider.name)
                log.warning("llm.provider_failed", provider=provider.name, error=str(exc))

        raise NoProviderAvailableError(
            f"All providers failed: {', '.join(errors)}"
        )

    async def complete_json(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1536,
    ) -> dict:
        """Completion parsed as JSON, tolerant of markdown code fences."""
        resp = await self.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format="json",
        )
        return _parse_json(resp.content)


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        # last resort: extract the outermost {...}
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1:
            return json.loads(cleaned[start : end + 1])
        raise


@lru_cache
def get_llm_router() -> LLMRouter:
    router = LLMRouter()
    log.info("llm.router_initialised", providers=router.provider_names)
    return router
