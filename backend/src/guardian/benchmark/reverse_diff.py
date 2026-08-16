"""Reverse a unified diff.

A security/bug *fix* applied backwards reconstructs the change that
introduced the flaw — turning every advisory-linked fix commit into a
labeled risky change. Binary patches cannot be reversed and are rejected.
"""

from __future__ import annotations

import re

_HUNK = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?P<context>.*)$"
)


class ReverseDiffError(ValueError):
    pass


def reverse_diff(diff_text: str) -> str:
    """Return the inverse diff (old⇄new swapped)."""
    if "GIT binary patch" in diff_text or "\nBinary files " in diff_text or diff_text.startswith("Binary files "):
        raise ReverseDiffError("binary diffs cannot be reversed")

    out: list[str] = []
    for line in diff_text.splitlines():
        hunk = _HUNK.match(line)
        if hunk:
            old = hunk.group("old_start") + ("," + hunk.group("old_count") if hunk.group("old_count") else "")
            new = hunk.group("new_start") + ("," + hunk.group("new_count") if hunk.group("new_count") else "")
            out.append(f"@@ -{new} +{old} @@{hunk.group('context')}")
        elif line.startswith("diff --git a/"):
            match = re.match(r"^diff --git a/(.+) b/(.+)$", line)
            if match:
                out.append(f"diff --git a/{match.group(2)} b/{match.group(1)}")
            else:
                out.append(line)
        elif line.startswith("--- a/"):
            out.append("+++ b/" + line[len("--- a/"):])
        elif line.startswith("+++ b/"):
            out.append("--- a/" + line[len("+++ b/"):])
        elif line == "--- /dev/null":
            out.append("+++ /dev/null")
        elif line == "+++ /dev/null":
            out.append("--- /dev/null")
        elif line.startswith("new file mode"):
            out.append("deleted file mode" + line[len("new file mode"):])
        elif line.startswith("deleted file mode"):
            out.append("new file mode" + line[len("deleted file mode"):])
        elif line.startswith("rename from "):
            out.append("rename to " + line[len("rename from "):])
        elif line.startswith("rename to "):
            out.append("rename from " + line[len("rename to "):])
        elif line.startswith("index "):
            match = re.match(r"^index ([0-9a-f.]+)\.\.([0-9a-f.]+)(.*)$", line)
            if match:
                out.append(f"index {match.group(2)}..{match.group(1)}{match.group(3)}")
            else:
                out.append(line)
        elif line.startswith("+"):
            out.append("-" + line[1:])
        elif line.startswith("-"):
            out.append("+" + line[1:])
        else:
            out.append(line)

    # Swapped +/- blocks keep git's remove-then-add convention readable enough
    # for parsers; ordering within a hunk does not affect line accounting.
    reversed_text = "\n".join(out)
    if diff_text.endswith("\n"):
        reversed_text += "\n"
    return reversed_text
