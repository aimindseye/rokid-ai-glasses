#!/usr/bin/env python3
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("test22_install_policy", HERE / "test22_install_policy.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


class InstallPolicyTests(unittest.TestCase):
    def test_vendor_denial_exact_observed_text(self):
        text = "adb: failed to install test22-debug.apk: error: not allow package install!\n"
        self.assertEqual(MOD.classify(text, 1), "BLOCKED_STANDARD_ADB_APK_INSTALL")

    def test_vendor_denial_without_exclamation(self):
        self.assertEqual(MOD.classify("Error: Not Allow Package Install", 1), "BLOCKED_STANDARD_ADB_APK_INSTALL")

    def test_android_user_restriction(self):
        self.assertEqual(MOD.classify("Failure [INSTALL_FAILED_USER_RESTRICTED]", 1), "BLOCKED_STANDARD_ADB_APK_INSTALL")

    def test_success(self):
        self.assertEqual(MOD.classify("Success\n", 0), "SUCCESS")

    def test_unknown_failure_stays_unknown(self):
        self.assertEqual(MOD.classify("Failure [INSTALL_FAILED_INVALID_APK]", 1), "UNCLASSIFIED_INSTALL_FAILURE")


if __name__ == "__main__":
    unittest.main()
