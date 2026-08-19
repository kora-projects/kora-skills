#!/usr/bin/env python3
"""Single source of truth for the kora-v1 plugin version.

Canonical version lives in plugins/kora-v1/.claude-plugin/plugin.json (the Claude Code
plugin manifest). Every other manifest must match it. This script reads, sets, and
verifies that invariant so the version is never hand-edited in seven places again.

Usage:
    python scripts/version.py              # print the canonical version
    python scripts/version.py get          # same
    python scripts/version.py check        # exit 1 if any target drifts from canonical
    python scripts/version.py set 0.3.0    # write 0.3.0 to canonical + all targets
    python scripts/version.py bump patch   # 0.2.0 -> 0.2.1  (also: minor, major)

No third-party dependencies (no jq, no PyYAML) — targeted regex edits that preserve each
file's existing formatting and key order.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The canonical manifest. Its version is the source of truth.
CANONICAL = "plugins/kora-v1/.claude-plugin/plugin.json"

# Every file that must carry the same version. JSON files: all `"version": "x.y.z"`
# occurrences. Markdown files: the `version:` key inside the YAML frontmatter.
JSON_TARGETS = [
    "plugins/kora-v1/.claude-plugin/plugin.json",
    "plugins/kora-v1/.codex-plugin/plugin.json",
    "plugins/kora-v1/skill.json",
    ".claude-plugin/marketplace.json",  # two occurrences: marketplace + plugin entry
]
MD_TARGETS = [
    "plugins/kora-v1/SKILL.md",
    "plugins/kora-v1/skills/kora-starter/SKILL.md",
]

SEMVER = r"\d+\.\d+\.\d+"
JSON_VERSION = re.compile(r'("version"\s*:\s*")' + SEMVER + r'(")')
MD_VERSION = re.compile(r'^(\s*version:\s*")' + SEMVER + r'(")', re.MULTILINE)


def read_canonical() -> str:
    text = (REPO / CANONICAL).read_text(encoding="utf-8")
    m = JSON_VERSION.search(text)
    if not m:
        sys.exit(f"error: no version found in {CANONICAL}")
    return re.search(SEMVER, m.group(0)).group(0)


def occurrences(path: Path, pattern: re.Pattern) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [re.search(SEMVER, m.group(0)).group(0) for m in pattern.finditer(text)]


def all_targets() -> list[tuple[Path, re.Pattern]]:
    return [(REPO / p, JSON_VERSION) for p in JSON_TARGETS] + \
           [(REPO / p, MD_VERSION) for p in MD_TARGETS]


def cmd_get() -> None:
    print(read_canonical())


def cmd_check() -> None:
    want = read_canonical()
    drift = []
    for path, pattern in all_targets():
        found = occurrences(path, pattern)
        if not found:
            drift.append(f"  {path.relative_to(REPO)}: no version field found")
        for v in found:
            if v != want:
                drift.append(f"  {path.relative_to(REPO)}: {v} (expected {want})")
    if drift:
        print(f"version drift from canonical {want}:")
        print("\n".join(drift))
        sys.exit(1)
    print(f"ok: all version fields at {want}")


def write_version(new: str) -> None:
    if not re.fullmatch(SEMVER, new):
        sys.exit(f"error: '{new}' is not a valid x.y.z version")
    changed = 0
    for path, pattern in all_targets():
        text = path.read_text(encoding="utf-8")
        updated, n = pattern.subn(rf"\g<1>{new}\g<2>", text)
        if n and updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed += 1
        if n:
            print(f"  {path.relative_to(REPO)}: {n} field(s) -> {new}")
    print(f"updated {changed} file(s) to {new}")


def cmd_set(new: str) -> None:
    write_version(new)


def cmd_bump(part: str) -> None:
    if part not in ("major", "minor", "patch"):
        sys.exit("error: bump expects one of: major, minor, patch")
    major, minor, patch = (int(x) for x in read_canonical().split("."))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    write_version(f"{major}.{minor}.{patch}")


def main(argv: list[str]) -> None:
    if not argv or argv[0] == "get":
        cmd_get()
    elif argv[0] == "check":
        cmd_check()
    elif argv[0] == "set" and len(argv) == 2:
        cmd_set(argv[1])
    elif argv[0] == "bump" and len(argv) == 2:
        cmd_bump(argv[1])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
