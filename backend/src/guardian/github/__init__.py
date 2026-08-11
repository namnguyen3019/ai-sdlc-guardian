"""GitHub integration: diff parsing now, webhook + API client in Week 3."""

from guardian.github.diff_parser import parse_diff
from guardian.github.pr_loader import load_pr

__all__ = ["parse_diff", "load_pr"]
