"""AI analysis through a provider abstraction (Amazon Bedrock by default).

The LLM is one more analyzer: it consumes the diff plus deterministic
findings and returns evidence-grounded ``Finding`` objects in the ``ai``
category. Repository code is untrusted input — instructions found inside it
are never followed, and findings whose evidence is absent from the diff are
discarded by the parser, not merely discouraged by the prompt.
"""

from guardian.bedrock.analyzer import AIAnalyzer
from guardian.bedrock.provider import LLMError, LLMProvider, LLMResponse, NullProvider, StubProvider

__all__ = ["AIAnalyzer", "LLMError", "LLMProvider", "LLMResponse", "NullProvider", "StubProvider"]
