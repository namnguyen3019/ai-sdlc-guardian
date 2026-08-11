"""LLM provider interface.

The core analysis path depends on this abstraction, never on boto3 directly,
so Guardian is not locked to Bedrock (development rule 15) and the AI path
stays testable offline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """One completion plus the usage accounting Guardian reports on."""

    text: str
    model_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    latency_ms: int = 0
    stop_reason: str = ""

    def estimated_cost_usd(
        self,
        price_input: float,
        price_output: float,
        price_cache_read: float,
    ) -> float:
        """Cost in USD from per-million-token prices.

        Cached reads are billed at the cache-read rate and are *not* also
        counted as ordinary input tokens.
        """
        return round(
            (self.input_tokens * price_input
             + self.output_tokens * price_output
             + self.cache_read_tokens * price_cache_read) / 1_000_000,
            6,
        )


class LLMError(RuntimeError):
    """Raised when a provider cannot produce a completion."""


class LLMProvider(ABC):
    """Minimal text-in/text-out contract.

    Deliberately narrow: no provider-specific parameters leak into the
    analysis layer, so a provider can be swapped without touching analyzers.
    """

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_system_prompt: bool = False,
    ) -> LLMResponse:
        """Return a completion, or raise :class:`LLMError`."""


class NullProvider(LLMProvider):
    """Provider that always fails — used when AI analysis is disabled."""

    def complete(self, *args: object, **kwargs: object) -> LLMResponse:
        raise LLMError("AI analysis is disabled (no provider configured)")


class StubProvider(LLMProvider):
    """Returns canned responses. For tests and offline development."""

    def __init__(self, responses: list[str] | str) -> None:
        self._responses = [responses] if isinstance(responses, str) else list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_system_prompt: bool = False,
    ) -> LLMResponse:
        self.calls.append((system, user))
        if not self._responses:
            raise LLMError("StubProvider has no responses left")
        text = self._responses.pop(0)
        return LLMResponse(
            text=text,
            model_id="stub",
            input_tokens=len(system) // 4 + len(user) // 4,
            output_tokens=len(text) // 4,
        )
