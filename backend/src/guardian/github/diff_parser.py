"""Parser for unified git diffs (the ``git diff`` / GitHub ``.diff`` format).

The parser never executes or evaluates diff content — repository code is
untrusted input and is only ever treated as data.

Known limitation: paths containing spaces that git quotes (``"a/my file"``)
are not un-escaped; they are rare in practice and only affect path
classification, not parsing safety.
"""

from __future__ import annotations

import re

from guardian.models.pr import ChangeType, DiffLine, FileChange

_DIFF_HEADER = re.compile(r"^diff --git a/(?P<a>.+) b/(?P<b>.+)$")
_HUNK_HEADER = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def parse_diff(diff_text: str) -> list[FileChange]:
    """Parse a unified diff into structured per-file changes."""
    files: list[FileChange] = []
    current: FileChange | None = None
    old_line = 0
    new_line = 0
    in_hunk = False
    patch_lines: list[str] = []

    def flush() -> None:
        nonlocal current, patch_lines
        if current is not None:
            current.patch = "\n".join(patch_lines)
            files.append(current)
        current = None
        patch_lines = []

    for line in diff_text.splitlines():
        header = _DIFF_HEADER.match(line)
        if header:
            flush()
            in_hunk = False
            current = FileChange(path=header.group("b"), old_path=header.group("a"))
            patch_lines.append(line)
            continue

        if current is None:
            continue

        patch_lines.append(line)

        if not in_hunk:
            if line.startswith("new file mode"):
                current.change_type = ChangeType.ADDED
                continue
            if line.startswith("deleted file mode"):
                current.change_type = ChangeType.DELETED
                continue
            if line.startswith("rename from "):
                current.change_type = ChangeType.RENAMED
                current.old_path = line[len("rename from "):]
                continue
            if line.startswith("rename to "):
                current.path = line[len("rename to "):]
                continue
            if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
                current.is_binary = True
                continue
            if line.startswith("+++ b/"):
                current.path = line[len("+++ b/"):]
                continue
            if line.startswith("--- a/") or line in ("--- /dev/null", "+++ /dev/null"):
                continue

        hunk = _HUNK_HEADER.match(line)
        if hunk:
            in_hunk = True
            old_line = int(hunk.group("old_start"))
            new_line = int(hunk.group("new_start"))
            continue

        if not in_hunk:
            continue

        if line.startswith("+"):
            current.added_lines.append(DiffLine(line_number=new_line, content=line[1:]))
            current.additions += 1
            new_line += 1
        elif line.startswith("-"):
            current.removed_lines.append(DiffLine(line_number=old_line, content=line[1:]))
            current.deletions += 1
            old_line += 1
        elif line.startswith("\\"):
            pass  # "\ No newline at end of file"
        else:
            old_line += 1
            new_line += 1

    flush()

    # DELETED files keep their meaningful path from the "a/" side.
    for change in files:
        if change.change_type == ChangeType.DELETED and change.old_path:
            change.path = change.old_path
        if change.change_type != ChangeType.RENAMED and change.old_path == change.path:
            change.old_path = None
    return files
