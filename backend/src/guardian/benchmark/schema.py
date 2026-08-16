"""Benchmark record schema.

A record is one labeled pull-request-shaped change: a diff plus ground truth.
The diff itself lives in a sidecar ``<id>.diff`` file; the JSONL dataset file
holds everything else.
"""

from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

# Fraction of records assigned to the untouchable holdout split (deterministic).
_HOLDOUT_BUCKETS = 3  # of 10 → 30%


class BenchmarkCategory(str, Enum):
    SECURITY = "security"
    BUG = "bug"
    AUTH_CHANGE = "auth_change"
    DATABASE_CHANGE = "database_change"
    API_CHANGE = "api_change"
    TESTING_DEFICIENCY = "testing_deficiency"
    NORMAL = "normal"


class SourceKind(str, Enum):
    CURATED_OSV = "curated_osv"        # advisory-backed (OSV/GHSA)
    CURATED_DATASET = "curated_dataset"  # research dataset (SWE-bench, BugsInPy, …)
    MINED = "mined"                    # sampled from repository history
    SYNTHETIC = "synthetic"            # seeded pattern; report separately


class DiffDirection(str, Enum):
    AS_MERGED = "as_merged"      # the change as it was proposed/merged
    REVERSED_FIX = "reversed_fix"  # a fix applied backwards → introduces the flaw


class LabelStatus(str, Enum):
    CONFIRMED = "confirmed"  # historical evidence or verified by a human
    CANDIDATE = "candidate"  # heuristic label; excluded from evaluation


class Split(str, Enum):
    CALIBRATION = "calibration"  # may be inspected while tuning
    HOLDOUT = "holdout"          # untouched until the final evaluation run


class Provenance(BaseModel):
    repository: str = ""            # owner/name
    commit_sha: str = ""
    pr_number: int | None = None
    advisory_id: str = ""           # e.g. GHSA-xxxx / CVE-xxxx
    cwe_ids: list[str] = Field(default_factory=list)
    license_spdx: str = ""          # license of the source repo
    retrieved_at: str = ""          # ISO date the artifact was fetched
    url: str = ""


class BenchmarkRecord(BaseModel):
    schema_version: int = SCHEMA_VERSION
    id: str                                  # unique, stable; names the diff file
    category: BenchmarkCategory
    is_risky: bool
    source: SourceKind
    direction: DiffDirection = DiffDirection.AS_MERGED
    label_status: LabelStatus = LabelStatus.CANDIDATE
    # Deterministic rule ids Guardian is expected to fire (optional, rule-level
    # ground truth for finding-level metrics).
    expected_rules: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    notes: str = ""

    @property
    def diff_filename(self) -> str:
        return f"{self.id}.diff"

    @property
    def split(self) -> Split:
        """Deterministic split from the record id — not stored, not editable.

        sha256 keeps the assignment stable across machines and Python builds,
        so nobody can quietly re-roll a record into the convenient split.
        """
        digest = hashlib.sha256(self.id.encode("utf-8")).digest()
        return Split.HOLDOUT if digest[0] % 10 < _HOLDOUT_BUCKETS else Split.CALIBRATION
