"""Finding models — the structured output of every analyzer."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}[self.value]


class Category(str, Enum):
    SECURITY = "security"
    TESTING = "testing"
    COMPLEXITY = "complexity"
    CHANGE_IMPACT = "change_impact"
    DEPENDENCY = "dependency"
    AI = "ai"


class FindingSource(str, Enum):
    DETERMINISTIC = "deterministic"
    AI = "ai"


class Finding(BaseModel):
    """One concrete, explainable risk observation.

    Every finding must carry a machine-readable ``rule`` id, a human-readable
    ``reason``, and an actionable ``recommendation``. AI findings must also
    carry ``evidence`` quoting the diff they are based on.
    """

    category: Category
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    file: str | None = None
    line: int | None = None
    rule: str
    title: str | None = None
    reason: str
    recommendation: str
    evidence: str | None = None
    source: FindingSource = FindingSource.DETERMINISTIC
