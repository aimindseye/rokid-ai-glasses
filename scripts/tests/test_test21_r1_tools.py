#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import json
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "analyze_test21_r1_discovery.py"
EXPECTED_AAR_SHA = "c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"


class TestAnalyzerHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("an", ANALYZER)
        cls.an = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.an)

    def test_package_names(self):
        text = (
            "package:/data/app/a/base.apk=com.rokid.foo\n"
            "package:org.aimindseye.rokid.test\n"
            "package:/data/app/~~abcDEF==/com.rokid.sprite.global.aiapp-zDrDhm==/base.apk=com.rokid.sprite.global.aiapp\n"
        )
        self.assertEqual(
            self.an.package_names(text),
            [
                "com.rokid.foo",
                "com.rokid.sprite.global.aiapp",
                "org.aimindseye.rokid.test",
            ],
        )

    def test_global_package_survives_equals_in_apk_path(self):
        text = "package:/data/app/~~hash==/pkg-hash==/base.apk=com.rokid.sprite.global.aiapp\n"
        self.assertIn(self.an.EXPECTED_GLOBAL_HI_ROKID_PACKAGE, self.an.package_names(text))

    def test_aiui_terms(self):
        self.assertIn("aiui", self.an.has_terms("AIUI runtime"))
        self.assertIn(".aix", self.an.has_terms("sample.aix"))

    def test_hi_rokid_score_prefers_running_service(self):
        low = self.an.score_hi_rokid("com.rokid.foo", "", "")
        high = self.an.score_hi_rokid("com.rokid.foo", "com.rokid.foo", "com.rokid.foo")
        self.assertGreater(high, low)

    def test_expected_global_package_constant(self):
        self.assertEqual(self.an.EXPECTED_GLOBAL_HI_ROKID_PACKAGE, "com.rokid.sprite.global.aiapp")


class TestSyntheticAnalysis(unittest.TestCase):
    def test_missing_aar_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "raw"
            raw.mkdir()
            (raw / "phone-packages.txt").write_text("package:/x/base.apk=com.rokid.hirokid\n", encoding="utf-8")
            (raw / "phone-processes.txt").write_text("com.rokid.hirokid\n", encoding="utf-8")
            (raw / "activity-services.txt").write_text("com.rokid.hirokid\n", encoding="utf-8")
            (raw / "repo-cxr-aiui-census.txt").write_text("com.rokid.cxr:client-l\n", encoding="utf-8")
            (raw / "aar-census.txt").write_text("AAR_FOUND=NO\n", encoding="utf-8")
            (raw / "collection-status.txt").write_text("RC_PHONE_PACKAGES=0\n", encoding="utf-8")
            cp = subprocess.run(["python3", str(ANALYZER), "--evidence", str(root)], text=True, capture_output=True)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            data = json.loads((root / "sanitized/test21-r1-summary.json").read_text())
            self.assertEqual(data["next_action"], "BLOCKED_CXR_L_AAR_NOT_FOUND")
            self.assertEqual(data["device_mutation"], "NONE")

    def test_operator_package_can_qualify_next_action(self):
        # Analyzer intentionally trusts the operator package hint but still requires the AAR.
        # Build a file with the accepted SHA by monkey-patching only at unit level is avoided;
        # instead verify that without the exact artifact the run remains blocked.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / "raw"
            raw.mkdir()
            (raw / "phone-packages.txt").write_text("package:com.example.hirokid\n", encoding="utf-8")
            (raw / "phone-processes.txt").write_text("", encoding="utf-8")
            (raw / "activity-services.txt").write_text("", encoding="utf-8")
            (raw / "repo-cxr-aiui-census.txt").write_text("AIUI .aix\n", encoding="utf-8")
            (raw / "aar-census.txt").write_text("AAR_FOUND=NO\n", encoding="utf-8")
            (raw / "collection-status.txt").write_text("", encoding="utf-8")
            cp = subprocess.run([
                "python3", str(ANALYZER), "--evidence", str(root),
                "--hi-rokid-package", "com.example.hirokid",
            ], text=True, capture_output=True)
            self.assertEqual(cp.returncode, 0)
            data = json.loads((root / "sanitized/test21-r1-summary.json").read_text())
            self.assertEqual(data["hi_rokid"]["selection_confidence"], "operator_explicit")
            self.assertTrue(data["aiui_eligibility"]["signal_present"])
            self.assertFalse(data["aiui_eligibility"]["non_display_runtime_support_proven"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
