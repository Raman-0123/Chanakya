"""Core LLM types and the provider interface."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LLMMessage:
    role: Role
    content: str

    def as_openai(self) -> dict[str, str]:
        return {"role": self.role.value, "content": self.content}


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    latency_ms: int = 0
    tokens_in: int | None = None
    tokens_out: int | None = None
    finish_reason: str | None = None
    raw: dict | None = field(default=None, repr=False)


class LLMProviderError(RuntimeError):
    """Raised when a single provider fails; the router will try the next."""

    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class BaseLLMProvider(abc.ABC):
    """Contract every provider adapter implements."""

    name: str
    model: str

    @abc.abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        response_format: Literal["text", "json"] = "text",
    ) -> LLMResponse:
        """Return a single completion or raise LLMProviderError."""

    @property
    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True when this provider has the credentials it needs."""
