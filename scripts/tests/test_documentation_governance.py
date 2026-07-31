#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class GovernanceTests(unittest.TestCase):
    def make_repo(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "docs/consumer").mkdir(parents=True)
        (root / "docs/developer").mkdir(parents=True)
        (root / "docs/reference").mkdir(parents=True)
        (root / "docs/contributing").mkdir(parents=True)
        (root / "scripts/safety").mkdir(parents=True)
        checker = Path(__file__).resolve().parents[1] / "safety/check_documentation_governance.py"
        (root / "scripts/safety/check_documentation_governance.py").write_text(
            checker.read_text(encoding="utf-8"), encoding="utf-8"
        )
        page = """# Page\n\n<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->\n\n## Page status\n\n| Field | Value |\n|---|---|\n| Audience | Consumer |\n"""
        (root / "README.md").write_text(page.replace("# Page", "# Root", 1).replace("audience=consumer", "audience=all"), encoding="utf-8")
        (root / "docs/README.md").write_text(page.replace("# Page", "# Documentation", 1).replace("audience=consumer", "audience=all"), encoding="utf-8")
        (root / "docs/consumer/README.md").write_text(page.replace("# Page", "# Consumer", 1), encoding="utf-8")
        manifest = {
            "schema": "rokid-ai-glasses.wiki-navigation.v1",
            "device_scope": "rokid-ai-glasses-style-non-display",
            "landing_pages": [
                {"path": "README.md", "audience": "all"},
                {"path": "docs/README.md", "audience": "all"},
            ],
            "sections": [
                {"id": "consumer", "landing": "docs/consumer/README.md", "pages": ["docs/consumer/README.md"]}
            ],
            "legacy_redirects": [],
            "canonical_roots": ["docs/consumer", "docs/developer", "docs/reference", "docs/contributing"],
            "consumer_technical_boundary_heading": "Technical evidence",
        }
        (root / "docs/wiki-navigation.json").write_text(json.dumps(manifest), encoding="utf-8")
        return root

    def run_checker(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(root / "scripts/safety/check_documentation_governance.py"), "--repo", str(root)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_minimal_valid_repository(self) -> None:
        root = self.make_repo()
        result = self.run_checker(root)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_orphan_page_fails(self) -> None:
        root = self.make_repo()
        (root / "docs/consumer/orphan.md").write_text("# Orphan\n", encoding="utf-8")
        result = self.run_checker(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("orphan canonical page", result.stdout)


if __name__ == "__main__":
    unittest.main()
