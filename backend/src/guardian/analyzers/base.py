"""Analyzer contract. Every analyzer — deterministic or AI — consumes a
``PRContext`` plus extracted ``PRFeatures`` and returns structured findings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from guardian.models.config import GuardianConfig
from guardian.models.features import PRFeatures
from guardian.models.findings import Finding
from guardian.models.pr import PRContext


class BaseAnalyzer(ABC):
    name: ClassVar[str] = "base"

    def __init__(self, config: GuardianConfig | None = None) -> None:
        self.config = config or GuardianConfig()

    @abstractmethod
    def analyze(self, pr: PRContext, features: PRFeatures) -> list[Finding]:
        """Return zero or more findings. Must not raise on malformed input
        it can tolerate; unexpected exceptions are isolated by the service."""
