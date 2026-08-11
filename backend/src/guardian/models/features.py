"""Deterministic features extracted from a pull request diff."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PRFeatures(BaseModel):
    files_changed: int = 0
    lines_added: int = 0
    lines_deleted: int = 0

    source_files: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    database_files: list[str] = Field(default_factory=list)
    auth_files: list[str] = Field(default_factory=list)
    payment_files: list[str] = Field(default_factory=list)
    api_files: list[str] = Field(default_factory=list)
    dependency_files: list[str] = Field(default_factory=list)
    ci_files: list[str] = Field(default_factory=list)
    infra_files: list[str] = Field(default_factory=list)
    critical_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)

    @property
    def total_churn(self) -> int:
        return self.lines_added + self.lines_deleted

    @property
    def source_files_changed(self) -> int:
        return len(self.source_files)

    @property
    def test_files_changed(self) -> int:
        return len(self.test_files)

    @property
    def config_files_changed(self) -> int:
        return len(self.config_files)

    @property
    def database_files_changed(self) -> int:
        return len(self.database_files)

    @property
    def auth_files_changed(self) -> int:
        return len(self.auth_files)

    @property
    def api_files_changed(self) -> int:
        return len(self.api_files)

    @property
    def critical_modules_changed(self) -> int:
        return len(self.critical_files)
