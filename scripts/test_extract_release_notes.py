#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path

from extract_release_notes import extract_release_notes


class ExtractReleaseNotesTest(unittest.TestCase):
    def test_extracts_one_version_section_without_following_version(self) -> None:
        changelog = """# Changelog

## v1.2.3 - 2026-09-10

### 修复

- 中文更新说明

## v1.2.2 - 2026-09-01

- 旧版本内容
"""

        self.assertEqual(
            extract_release_notes(changelog, "v1.2.3"),
            "### 修复\n\n- 中文更新说明\n",
        )

    def test_accepts_bracketed_version_heading(self) -> None:
        self.assertEqual(
            extract_release_notes("## [v2.0.0]\n\n- 发布\n", "v2.0.0"),
            "- 发布\n",
        )

    def test_ignores_headings_inside_fenced_markdown(self) -> None:
        changelog = """## v1.0.0

```markdown
## v9.9.9

- 不是版本区块
```

- 正文

## v0.9.0
"""

        self.assertEqual(
            extract_release_notes(changelog, "v1.0.0"),
            "```markdown\n## v9.9.9\n\n- 不是版本区块\n```\n\n- 正文\n",
        )

    def test_rejects_missing_or_ambiguous_section(self) -> None:
        with self.assertRaisesRegex(ValueError, "no section"):
            extract_release_notes("# Changelog\n", "v1.0.0")
        with self.assertRaisesRegex(ValueError, "multiple sections"):
            extract_release_notes(
                "## v1.0.0\n\n- one\n\n## v1.0.0\n\n- two\n", "v1.0.0"
            )

    def test_current_changelog_has_extractable_v0175_notes(self) -> None:
        changelog = (
            Path(__file__)
            .parents[1]
            .joinpath("CHANGELOG.md")
            .read_text(encoding="utf-8")
        )

        notes = extract_release_notes(changelog, "v0.17.5")

        self.assertIn("SmartEdu", notes)
        self.assertNotIn("## v0.17.4", notes)


if __name__ == "__main__":
    unittest.main()
