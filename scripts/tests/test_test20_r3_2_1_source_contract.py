#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "check_test20_r3_2_1_source_contract.py"
PACKAGE = "org.aimindseye.rokid.cxrphotoqualification"
VERSION = "1.0-test20-r3.2"


class SourceContractTests(unittest.TestCase):
    def make_repo(self, body: str, *, permissions: tuple[str, ...] = ()) -> tuple[tempfile.TemporaryDirectory, Path]:
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        app = repo / "android-client" / "app"
        src = app / "src" / "main" / "java" / "org" / "aimindseye" / "rokid" / "cxrphotoqualification"
        src.mkdir(parents=True)
        (app / "build.gradle").write_text("plugins { id 'com.android.application' }\n", encoding="utf-8")
        permission_xml = "\n".join(f'    <uses-permission android:name="{p}" />' for p in permissions)
        (app / "src" / "main" / "AndroidManifest.xml").write_text(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
            + permission_xml
            + "\n    <application />\n</manifest>\n",
            encoding="utf-8",
        )
        (src / "MainActivity.java").write_text(
            "package org.aimindseye.rokid.cxrphotoqualification;\n"
            f'final class MainActivity {{ static final String VERSION = "{VERSION}"; void run(Client client) {{ {body} }} }}\n'
            "interface Client { void takePhoto(int a,int b,int c); void startAudioStream(); void stopAudioStream(); }\n",
            encoding="utf-8",
        )
        return td, repo

    def run_checker(self, repo: Path):
        output = repo / "report.json"
        result = subprocess.run(
            ["python3", str(CHECKER), "--repo", str(repo), "--output", str(output)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        payload = json.loads(output.read_text()) if output.exists() else None
        return result, payload

    def test_camera_and_record_audio_permissions_are_attested_not_rejected(self):
        td, repo = self.make_repo(
            "client.takePhoto(1920, 1080, 80);",
            permissions=("android.permission.CAMERA", "android.permission.RECORD_AUDIO"),
        )
        try:
            result, payload = self.run_checker(repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("TEST20_R3_2_1_SOURCE_CONTRACT=PASS", result.stdout)
            self.assertEqual(payload["take_photo_call_sites"], 1)
            self.assertEqual(payload["audio_start_call_sites"], 0)
            self.assertEqual(payload["audio_stop_call_sites"], 0)
            self.assertEqual(
                payload["declared_manifest_media_permissions"],
                ["android.permission.CAMERA", "android.permission.RECORD_AUDIO"],
            )
            self.assertEqual(payload["manifest_permission_interpretation"], "ATTEST_ONLY_NOT_EXECUTION_PROOF")
        finally:
            td.cleanup()

    def test_no_media_permissions_also_passes(self):
        td, repo = self.make_repo("client.takePhoto(1920, 1080, 80);")
        try:
            result, payload = self.run_checker(repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["declared_manifest_media_permissions"], [])
        finally:
            td.cleanup()

    def test_audio_start_call_fails_closed(self):
        td, repo = self.make_repo("client.takePhoto(1920,1080,80); client.startAudioStream();")
        try:
            result, _ = self.run_checker(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("audio operation call site", result.stderr)
        finally:
            td.cleanup()

    def test_audio_stop_call_fails_closed(self):
        td, repo = self.make_repo("client.takePhoto(1920,1080,80); client.stopAudioStream();")
        try:
            result, _ = self.run_checker(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("audio operation call site", result.stderr)
        finally:
            td.cleanup()

    def test_two_take_photo_calls_fail_closed(self):
        td, repo = self.make_repo("client.takePhoto(1920,1080,80); client.takePhoto(1920,1080,80);")
        try:
            result, _ = self.run_checker(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("expected exactly one", result.stderr)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
