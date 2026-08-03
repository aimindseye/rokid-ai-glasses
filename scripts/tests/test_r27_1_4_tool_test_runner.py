from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "scripts/research/canonical/tool_test_runner.py"
spec = importlib.util.spec_from_file_location("r2714_tool_test_runner", MOD_PATH)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
assert spec.loader is not None
spec.loader.exec_module(M)


class ToolTestRunnerContract(unittest.TestCase):
    def test_registry_counts(self):
        reg = M.load_registry()
        self.assertEqual(reg["profile_count"], 39)
        self.assertEqual(reg["current_equivalent_count"], 38)
        self.assertEqual(reg["deferred_count"], 1)
        self.assertEqual(len(reg["profiles"]), 39)

    def test_exact_deferred_missing_fixture_profile(self):
        p = M.find_profile("test21", "r3.3.4.2.6.1.1")
        self.assertEqual(p["status"], "DEFERRED_MISSING_FIXTURE")
        self.assertEqual(p["required_fixture_paths"], ["fixtures/synthetic-obfuscated-client-l-1.0.1.aar"])
        self.assertFalse((REPO / p["required_fixture_paths"][0]).exists())

    def test_lightweight_current_profile_runs_through_canonical_dispatch(self):
        r = M.run_profile(REPO, "test21", "r3.2", emit_output=False)
        self.assertTrue(r.source_lock)
        self.assertEqual(r.status, "CURRENT_EQUIVALENT")
        self.assertEqual(r.returncode, 0)
        self.assertIn("Ran 10 tests", r.stdout)
        self.assertIn("OK", r.stdout)

    def test_deferred_profile_refuses_default_execution(self):
        r = M.run_profile(REPO, "test21", "r3.3.4.2.6.1.1", emit_output=False)
        self.assertTrue(r.source_lock)
        self.assertEqual(r.returncode, 5)
        self.assertIn("DEFERRED:", r.stdout)

    def test_canonical_runner_has_no_device_execution_primitives(self):
        text = MOD_PATH.read_text(encoding="utf-8")
        for token in ("adb shell", "adb -s", "frida-server", "magisk", "su -c", "am force-stop"):
            self.assertNotIn(token, text)
        self.assertIn("DEVICE_OPERATION=NONE", text)


if __name__ == "__main__":
    unittest.main()
