"""Models describing a pull request and its diff."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class DiffLine(BaseModel):
    """A single added or removed line.

    ``line_number`` refers to the new file for added lines and the old file
    for removed lines.
    """

    line_number: int
    content: str


class FileChange(BaseModel):
    path: str
    change_type: ChangeType = ChangeType.MODIFIED
    old_path: str | None = None
    additions: int = 0
    deletions: int = 0
    is_binary: bool = False
    added_lines: list[DiffLine] = Field(default_factory=list)
    removed_lines: list[DiffLine] = Field(default_factory=list)
    patch: str = ""


class PRContext(BaseModel):
    """Everything Guardian knows about a pull request under analysis.

    Only the diff and lightweight metadata are carried around — never a full
    repository checkout. Repository code is treated as untrusted input.
    """

    repository: str = "unknown/unknown"
    pr_number: int = 0
    title: str = ""
    description: str = ""
    author: str = ""
    base_sha: str = ""
    head_sha: str = ""
    files: list[FileChange] = Field(default_factory=list)

    @property
    def total_additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def total_churn(self) -> int:
        return self.total_additions + self.total_deletions
