"""AI analyzer — an ordinary :class:`BaseAnalyzer` backed by an LLM provider.

Contract with the rest of the system:

* Its findings land in ``Category.AI`` and are scored by the deterministic
  engine like any others; the model never emits or influences the final score
  directly.
* Findings whose evidence is not present in the supplied diff are discarded
  (see :mod:`guardian.bedrock.parser`).
* Any provider failure raises; ``AnalysisService`` records it as an isolated
  analyzer failure and the deterministic analysis still completes.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from guardian.analyzers.base import BaseAnalyzer
from guardian.bedrock.parser import parse_findings
from guardian.bedrock.prompts import SYSTEM_PROMPT, build_user_message
from guardian.bedrock.provider import LLMProvider, LLMResponse
from guardian.models.config import GuardianConfig
from guardian.models.features import PRFeatures
from guardian.models.findings import Finding
from guardian.models.pr import PRContext

logger = logging.getLogger(__name__)


class AIAnalyzer(BaseAnalyzer):
    name: ClassVar[str] = "ai"

    def __init__(
        self,
        config: GuardianConfig | None = None,
        provider: LLMProvider | None = None,
        deterministic_findings: list[Finding] | None = None,
    ) -> None:
        super().__init__(config)
        if provider is None:
            from guardian.bedrock.client import BedrockProvider

            provider = BedrockProvider(self.config)
        self.provider = provider
        self.deterministic_findings = deterministic_findings or []
        self.last_response: LLMResponse | None = None
        self.last_rejected_ungrounded = 0
        self.last_rejected_malformed = 0

    def analyze(self, pr: PRContext, features: PRFeatures) -> list[Finding]:
        user_message = build_user_message(
            pr,
            features,
            self.deterministic_findings,
            max_diff_chars=self.config.ai_max_diff_chars,
        )
        response = self.provider.complete(
            system=SYSTEM_PROMPT,
            user=user_message,
            max_tokens=self.config.ai_max_tokens,
            temperature=self.config.ai_temperature,
            cache_system_prompt=self.config.ai_prompt_caching,
        )
        self.last_response = response

        diff_text = "\n".join(f.patch for f in pr.files if f.patch and not f.is_binary)
        result = parse_findings(response.text, diff_text)
        self.last_rejected_ungrounded = result.rejected_ungrounded
        self.last_rejected_malformed = result.rejected_malformed
        if result.rejected_total:
            logger.info(
                "AI analyzer dropped %d ungrounded and %d malformed finding(s)",
                result.rejected_ungrounded,
                result.rejected_malformed,
            )
        return result.findings
