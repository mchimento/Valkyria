#!/usr/bin/env python3
"""Bumps the version string in every file that has to carry it, per
CLAUDE.md's versioning ground rule: app/version.py (the single source of
truth) and packaging/windows/valkyria.iss (a separate static string Inno
Setup can't read from the Python source). Doesn't touch CHANGELOG.md —
moving [Unreleased]'s contents under a dated release heading needs a
human/Claude decision about what belongs there, not a blind bump.

Usage: python scripts/bump_version.py <new-version>
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+")

FILES = [
    (REPO_ROOT / "app" / "version.py", re.compile(r'__version__\s*=\s*"([^"]+)"')),
    (REPO_ROOT / "packaging" / "windows" / "valkyria.iss", re.compile(r'#define MyAppVersion "([^"]+)"')),
]


def bump_file(path: Path, pattern: re.Pattern, new_version: str) -> None:
    text = path.read_text()
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        print(f"Error: expected exactly one version match in {path}, found {len(matches)}", file=sys.stderr)
        sys.exit(1)
    match = matches[0]
    old_version = match.group(1)
    start, end = match.span(1)
    path.write_text(text[:start] + new_version + text[end:])
    print(f"{path.relative_to(REPO_ROOT)}: {old_version} -> {new_version}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump_version.py <new-version>", file=sys.stderr)
        sys.exit(1)

    new_version = sys.argv[1]
    if not VERSION_RE.match(new_version):
        print(f"Error: {new_version!r} doesn't look like a version (expected e.g. 1.2.3)", file=sys.stderr)
        sys.exit(1)

    for path, pattern in FILES:
        if not path.exists():
            print(f"Error: {path} not found", file=sys.stderr)
            sys.exit(1)
        bump_file(path, pattern, new_version)

    print("Remember to also move CHANGELOG.md's [Unreleased] section under a new dated release heading.")


if __name__ == "__main__":
    main()
