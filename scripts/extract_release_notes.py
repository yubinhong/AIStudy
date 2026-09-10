#!/usr/bin/env python3
"""Extract the exact version section used as a GitHub Release body."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VERSION_HEADING = re.compile(
    r"^##\s+\[?(v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\]?(?:\s+-\s+.*)?\s*$"
)
TAG_NAME = re.compile(r"^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _version_headings(lines: list[str]) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    in_fenced_block = False
    for index, line in enumerate(lines):
        if line.startswith(("```", "~~~")):
            in_fenced_block = not in_fenced_block
            continue
        if not in_fenced_block:
            match = VERSION_HEADING.fullmatch(line)
            if match is not None:
                headings.append((index, match.group(1)))
    return headings


def extract_release_notes(changelog: str, tag: str) -> str:
    """Return the non-empty Markdown body for exactly one version heading."""

    if not TAG_NAME.fullmatch(tag):
        raise ValueError(f"invalid release tag: {tag!r}")

    lines = changelog.splitlines()
    headings = _version_headings(lines)
    matches = [index for index, heading_tag in headings if heading_tag == tag]
    if not matches:
        raise ValueError(f"CHANGELOG.md has no section for {tag}")
    if len(matches) > 1:
        raise ValueError(f"CHANGELOG.md has multiple sections for {tag}")

    start = matches[0] + 1
    end = len(lines)
    in_fenced_block = False
    for index in range(start, len(lines)):
        line = lines[index]
        if line.startswith(("```", "~~~")):
            in_fenced_block = not in_fenced_block
            continue
        if not in_fenced_block and line.startswith("## "):
            end = index
            break
    notes = "\n".join(lines[start:end]).strip()
    if not notes:
        raise ValueError(f"CHANGELOG.md section for {tag} is empty")
    return f"{notes}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="version tag, for example v0.17.4")
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="path to CHANGELOG.md",
    )
    args = parser.parse_args()
    try:
        changelog = args.changelog.read_text(encoding="utf-8")
        notes = extract_release_notes(changelog, args.tag)
    except (OSError, UnicodeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
