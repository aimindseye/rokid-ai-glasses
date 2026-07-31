#!/usr/bin/env python3
from __future__ import annotations

import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "fixtures/synthetic/test19-r2"
EVENT_ANALYZER = ROOT / "scripts/tests/analyze_test19_r2_events.py"
NETWORK_ANALYZER = ROOT / "scripts/tests/analyze_test19_r2_network.py"
RESOLVER = ROOT / "scripts/research/cxr/resolve_cxr_l_maven.py"
APP = ROOT / "android-client/test19r2/src/main/java/org/aimindseye/rokid/cxrlqualification"


class Test19R2Tools(unittest.TestCase):
    def run_events(self, fixture: str) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as temp_value:
            temp = Path(temp_value)
            summary = temp / "summary.json"
            completed = subprocess.run([
                "python3", str(EVENT_ANALYZER),
                "--events", str(FIX / fixture),
                "--host-recovery", str(FIX / "host-recovery-pass.json"),
                "--summary-json", str(summary),
                "--summary-md", str(temp / "summary.md"),
            ], check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            return completed.returncode, json.loads(summary.read_text())

    def test_pass_events(self) -> None:
        code, summary = self.run_events("connection-pass.jsonl")
        self.assertEqual(code, 0)
        self.assertTrue(summary["qualification_pass"])

    def test_failed_authorization_is_bounded(self) -> None:
        code, summary = self.run_events("connection-fail.jsonl")
        self.assertEqual(code, 10)
        self.assertFalse(summary["qualification_pass"])

    def test_network_pass_separates_stock_traffic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_value:
            out = Path(temp_value) / "network.json"
            completed = subprocess.run([
                "python3", str(NETWORK_ANALYZER), "--csv", str(FIX / "network-pass.csv"), "--output", str(out)
            ], check=False)
            value = json.loads(out.read_text())
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(value["counts"]["custom_public"], 0)
            self.assertEqual(value["counts"]["hi_rokid_public"], 1)

    def test_network_custom_public_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_value:
            out = Path(temp_value) / "network.json"
            completed = subprocess.run([
                "python3", str(NETWORK_ANALYZER), "--csv", str(FIX / "network-fail.csv"), "--output", str(out)
            ], check=False)
            self.assertEqual(completed.returncode, 10)

    def test_network_without_app_identity_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_value:
            out = Path(temp_value) / "network.json"
            completed = subprocess.run([
                "python3", str(NETWORK_ANALYZER), "--csv", str(FIX / "network-blocked.csv"), "--output", str(out)
            ], check=False)
            self.assertEqual(completed.returncode, 30)


    @unittest.skipUnless(shutil.which("javac") and shutil.which("jar"), "JDK tools required")
    def test_maven_resolver_and_api_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_value:
            temp = Path(temp_value)
            sources = temp / "src"
            classes = temp / "classes"
            classes.mkdir()
            java_sources = {
                "android/content/Context.java": "package android.content; public class Context {}",
                "com/rokid/cxr/link/utils/CxrDefs.java": "package com.rokid.cxr.link.utils; public class CxrDefs { public enum CXRSessionType { CUSTOMAPP } public static class CXRSession { public CXRSession(CXRSessionType t,String p){} } }",
                "com/rokid/cxr/link/callbacks/ICXRLinkCbk.java": "package com.rokid.cxr.link.callbacks; public interface ICXRLinkCbk { void onCXRLConnected(boolean b); void onGlassBtConnected(boolean b); void onGlassAiAssistStart(); void onGlassAiAssistStop(); }",
                "com/rokid/sprite/aiapp/externalapp/example/ExternalAppClient.java": "package com.rokid.sprite.aiapp.externalapp.example; import android.content.Context; import com.rokid.cxr.link.callbacks.ICXRLinkCbk; import com.rokid.cxr.link.utils.CxrDefs; public class ExternalAppClient { public ExternalAppClient(Context c){} public final void setCXRLinkCbk(ICXRLinkCbk c){} public final boolean configCXRSession(CxrDefs.CXRSession s){return true;} public final boolean connect(String t){return true;} public final void disconnect(){} }",
                "com/rokid/cxr/link/CXRLink.java": "package com.rokid.cxr.link; import android.content.Context; import com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient; public class CXRLink extends ExternalAppClient { public CXRLink(Context c){super(c);} }",
            }
            files=[]
            for relative, text in java_sources.items():
                path=sources/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                files.append(str(path))
            subprocess.run(["javac", "-d", str(classes), *files], check=True)
            jar_path=temp/"classes.jar"
            subprocess.run(["jar", "cf", str(jar_path), "-C", str(classes), "."], check=True)
            repo=temp/"repo/com/rokid/cxr/client-l/1.0.1"
            repo.mkdir(parents=True)
            with zipfile.ZipFile(repo/"client-l-1.0.1.aar", "w") as archive:
                archive.write(jar_path, "classes.jar")
            (repo/"client-l-1.0.1.pom").write_text("<project/>", encoding="utf-8")
            handler=functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(temp/"repo"))
            server=http.server.ThreadingHTTPServer(("127.0.0.1",0), handler)
            thread=threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                output=temp/"output"
                completed=subprocess.run([
                    "python3", str(RESOLVER), "--version", "1.0.1",
                    "--repository", f"http://127.0.0.1:{server.server_port}",
                    "--output", str(output),
                    "--javap", shutil.which("javap"),
                    "--expected-aar-sha256", hashlib.sha256((repo/"client-l-1.0.1.aar").read_bytes()).hexdigest(),
                    "--expected-pom-sha256", hashlib.sha256((repo/"client-l-1.0.1.pom").read_bytes()).hexdigest(),
                ], check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(completed.returncode, 0, completed.stdout)
                result=json.loads((output/"cxr-l-artifact-attestation.json").read_text())
                self.assertTrue(result["required_classes_complete"])
                self.assertTrue(result["required_methods_complete"])
                self.assertTrue(result["exact_artifact_hashes_complete"])
                self.assertEqual(
                    result["cxr_link_superclass"],
                    "com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient",
                )
                self.assertEqual(result["direct_cxr_link_required_method_count"], 0)
                self.assertEqual(result["required_effective_method_count"], 4)
                self.assertEqual(
                    set(result["method_declaring_classes"].values()),
                    {"com.rokid.sprite.aiapp.externalapp.example.ExternalAppClient"},
                )
                self.assertFalse(result["glass_info_class_present"])
                self.assertEqual(
                    set(result["required_callback_methods"]),
                    {
                        "onCXRLConnected",
                        "onGlassBtConnected",
                        "onGlassAiAssistStart",
                        "onGlassAiAssistStop",
                    },
                )
                self.assertNotIn("onGlassDeviceInfo", result["callback_methods"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


    def test_resolver_attests_inherited_methods_and_exact_descriptors(self) -> None:
        text = RESOLVER.read_text(encoding="utf-8")
        self.assertIn("EXPECTED_AAR_SHA256", text)
        self.assertIn("EXPECTED_POM_SHA256", text)
        self.assertIn("parse_superclass", text)
        self.assertIn("method_declaring_classes", text)
        self.assertIn("(Ljava/lang/String;)Z", text)
        self.assertIn("(Lcom/rokid/cxr/link/callbacks/ICXRLinkCbk;)V", text)

    def test_prepare_does_not_report_false_install_failure_after_resolver_failure(self) -> None:
        text = (ROOT / "scripts/tests/prepare_test19_r2.sh").read_text(encoding="utf-8")
        self.assertIn('if [ "$INSTALL_SUCCEEDED" = "YES" ]; then', text)
        self.assertIn('echo "PHONE_MUTATION=$PHONE_MUTATION_VALUE"', text)

    def test_source_has_no_media_or_upload_calls(self) -> None:
        text = "\n".join(path.read_text(encoding="utf-8") for path in APP.glob("*.java"))
        for forbidden in ("appUploadAndInstall", "takePhoto(", "startAudio", "customViewOpen"):
            self.assertNotIn(forbidden, text)
        self.assertIn("single_attempt_enforced", text)
        self.assertIn("AUTH_TOKEN_EXTRA", text)
        self.assertNotIn("rokid.clientSecret", text)

    def test_old_runner_is_disabled(self) -> None:
        text = (ROOT / "scripts/tests/run_test19_cxr_qualification.sh").read_text(encoding="utf-8")
        self.assertIn("TEST19_R1_WITHDRAWN", text)


if __name__ == "__main__":
    unittest.main()
