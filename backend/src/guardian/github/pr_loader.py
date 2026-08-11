"""Build a :class:`PRContext` from local inputs (Week 1 CLI mode).

Week 3 adds a GitHub API loader with webhook signature verification; both
produce the same ``PRContext`` so the analysis pipeline does not change.
"""

from __future__ import annotations

import json
from pathlib import Path

from guardian.github.diff_parser import parse_diff
from guardian.models.pr import PRContext

_META_FIELDS = {
    "repository",
    "pr_number",
    "title",
    "description",
    "author",
    "base_sha",
    "head_sha",
}


def load_pr(diff_path: str | Path, meta_path: str | Path | None = None, **overrides: object) -> PRContext:
    """Load a PR from a diff file plus optional JSON metadata and overrides."""
    diff_text = Path(diff_path).read_text(encoding="utf-8", errors="replace")
    meta: dict[str, object] = {}
    if meta_path is not None:
        raw = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"PR metadata in {meta_path} must be a JSON object")
        meta = {k: v for k, v in raw.items() if k in _META_FIELDS}
    meta.update({k: v for k, v in overrides.items() if v is not None})
    return PRContext(files=parse_diff(diff_text), **meta)
