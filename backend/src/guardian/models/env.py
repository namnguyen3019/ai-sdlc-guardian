"""Build GuardianConfig from environment variables (the Lambda config path)."""

from __future__ import annotations

import os

from guardian.models.config import GuardianConfig


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def config_from_env() -> GuardianConfig:
    defaults = GuardianConfig()
    return GuardianConfig(
        ai_enabled=_bool("GUARDIAN_AI_ENABLED", defaults.ai_enabled),
        bedrock_model_id=os.environ.get("GUARDIAN_BEDROCK_MODEL_ID", defaults.bedrock_model_id),
        bedrock_region=os.environ.get("GUARDIAN_BEDROCK_REGION", defaults.bedrock_region),
        ai_prompt_caching=_bool("GUARDIAN_AI_PROMPT_CACHING", defaults.ai_prompt_caching),
        ai_escalation_gate=_bool("GUARDIAN_AI_ESCALATION_GATE", defaults.ai_escalation_gate),
        dynamodb_table=os.environ.get("GUARDIAN_TABLE", defaults.dynamodb_table),
        reports_bucket=os.environ.get("GUARDIAN_BUCKET", defaults.reports_bucket),
        metrics_namespace=os.environ.get("GUARDIAN_METRICS_NAMESPACE", defaults.metrics_namespace),
    )
