from pathlib import Path

import pytest

from guardian.models.pr import ChangeType, DiffLine, FileChange, PRContext

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


def make_file(
    path: str,
    added: list[tuple[int, str]] | None = None,
    removed: list[tuple[int, str]] | None = None,
    change_type: ChangeType = ChangeType.MODIFIED,
) -> FileChange:
    added_lines = [DiffLine(line_number=n, content=c) for n, c in (added or [])]
    removed_lines = [DiffLine(line_number=n, content=c) for n, c in (removed or [])]
    return FileChange(
        path=path,
        change_type=change_type,
        added_lines=added_lines,
        removed_lines=removed_lines,
        additions=len(added_lines),
        deletions=len(removed_lines),
    )


def make_pr(*files: FileChange, **kwargs) -> PRContext:
    return PRContext(repository="acme/shop", pr_number=1, files=list(files), **kwargs)
