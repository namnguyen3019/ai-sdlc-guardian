"""Configuration models. Weights and patterns are configurable; risk-level
boundaries (0-30/31-60/61-80/81-100) are fixed product semantics."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class ScoringWeights(BaseModel):
    """Relative weight of each scoring dimension.

    Weights are normalized at scoring time over the dimensions that actually
    produced a signal (e.g. when AI analysis is unavailable, its weight is
    redistributed proportionally instead of silently deflating the score).
    """

    security: float = 0.30
    testing: float = 0.25
    change_impact: float = 0.20
    complexity: float = 0.15
    ai_risk: float = 0.10

    @model_validator(mode="after")
    def _non_negative(self) -> "ScoringWeights":
        values = self.model_dump()
        if any(v < 0 for v in values.values()):
            raise ValueError("scoring weights must be non-negative")
        if sum(values.values()) <= 0:
            raise ValueError("at least one scoring weight must be positive")
        return self


class GuardianConfig(BaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)

    # Severity → points contributed to a dimension score (before confidence).
    severity_points: dict[str, int] = Field(
        default_factory=lambda: {"LOW": 6, "MEDIUM": 14, "HIGH": 28, "CRITICAL": 45}
    )

    # Extra path fragments that mark a file as a critical module for this repo.
    critical_module_patterns: list[str] = Field(default_factory=list)

    # Thresholds used by deterministic analyzers.
    large_pr_lines: int = 500
    very_large_pr_lines: int = 1000
    large_pr_files: int = 20
    untested_source_lines: int = 30

    # --- AI analysis (Week 2) ---------------------------------------------
    ai_enabled: bool = True
    bedrock_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_region: str = "us-east-1"
    ai_max_tokens: int = 4096
    ai_temperature: float = 0.0
    ai_max_retries: int = 3

    # Only this many characters of diff are sent to the model. Guardian
    # analyzes the diff, never the repository, and truncates defensively so a
    # huge PR cannot blow up latency or cost.
    ai_max_diff_chars: int = 60_000

    # Cache the static system prompt. Bedrock supports manual cache points;
    # note the minimum cacheable prefix differs by model (Sonnet 1024 tokens,
    # Haiku 4.5 4096), and an undersized prefix caches silently as zero.
    ai_prompt_caching: bool = True

    # Optional cost control: skip the model entirely on PRs that deterministic
    # analysis already considers clearly low risk. Off by default so scoring
    # semantics match the specified architecture unless explicitly enabled.
    ai_escalation_gate: bool = False
    ai_gate_max_deterministic_score: int = 20
    ai_gate_max_churn: int = 100

    # USD per million tokens, used for the estimated-cost metric only.
    ai_price_per_mtok_input: float = 3.0
    ai_price_per_mtok_output: float = 15.0
    ai_price_per_mtok_cache_read: float = 0.30

    # --- Storage / observability ------------------------------------------
    dynamodb_table: str = "guardian-analyses"
    reports_bucket: str = ""
    metrics_namespace: str = "AiSdlcGuardian"


def load_config(path: str | Path | None = None) -> GuardianConfig:
    """Load configuration from a JSON file, or return defaults."""
    if path is None:
        return GuardianConfig()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return GuardianConfig.model_validate(raw)
