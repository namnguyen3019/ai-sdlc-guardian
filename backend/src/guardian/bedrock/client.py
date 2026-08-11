"""Amazon Bedrock implementation of :class:`LLMProvider` (Converse API).

boto3 is imported lazily so the core engine and its tests never require AWS
dependencies. Retries use exponential backoff on throttling; the caller
(AnalysisService) treats any final failure as a non-fatal analyzer failure.
"""

from __future__ import annotations

import logging
import time

from guardian.bedrock.provider import LLMError, LLMProvider, LLMResponse
from guardian.models.config import GuardianConfig

logger = logging.getLogger(__name__)

_RETRYABLE = {"ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException"}


class BedrockProvider(LLMProvider):
    def __init__(self, config: GuardianConfig | None = None, client: object | None = None) -> None:
        self.config = config or GuardianConfig()
        self._client = client  # injected in tests

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover
                raise LLMError(
                    "boto3 is required for Bedrock: pip install 'ai-sdlc-guardian[aws]'"
                ) from exc
            self._client = boto3.client("bedrock-runtime", region_name=self.config.bedrock_region)
        return self._client

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_system_prompt: bool = False,
    ) -> LLMResponse:
        system_blocks: list[dict] = [{"text": system}]
        if cache_system_prompt:
            # Manual cache point (Bedrock has no automatic caching). Minimum
            # cacheable prefix varies by model; an undersized prefix is
            # silently not cached — verify via usage counters, never assume.
            system_blocks.append({"cachePoint": {"type": "default"}})

        request = {
            "modelId": self.config.bedrock_model_id,
            "system": system_blocks,
            "messages": [{"role": "user", "content": [{"text": user}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        }

        last_error: Exception | None = None
        for attempt in range(self.config.ai_max_retries):
            started = time.monotonic()
            try:
                response = self.client.converse(**request)
                return self._to_response(response, round((time.monotonic() - started) * 1000))
            except Exception as exc:  # boto3 ClientError and friends
                error_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                last_error = exc
                if error_code in _RETRYABLE and attempt < self.config.ai_max_retries - 1:
                    delay = 2**attempt
                    logger.warning("bedrock %s, retrying in %ss", error_code, delay)
                    time.sleep(delay)
                    continue
                raise LLMError(f"Bedrock converse failed: {exc}") from exc
        raise LLMError(f"Bedrock converse failed after retries: {last_error}")

    def _to_response(self, response: dict, latency_ms: int) -> LLMResponse:
        try:
            content = response["output"]["message"]["content"]
            text = "".join(block.get("text", "") for block in content)
        except (KeyError, TypeError) as exc:
            raise LLMError(f"unexpected Bedrock response shape: {exc}") from exc
        usage = response.get("usage", {})
        return LLMResponse(
            text=text,
            model_id=self.config.bedrock_model_id,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            cache_read_tokens=usage.get("cacheReadInputTokens", 0),
            cache_write_tokens=usage.get("cacheWriteInputTokens", 0),
            latency_ms=latency_ms,
            stop_reason=response.get("stopReason", ""),
        )
