#!/usr/bin/env python3
from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
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


    def test_gradle_modules_require_only_their_own_properties(self) -> None:
        cxrm = (ROOT / "android-client/test19/build.gradle.kts").read_text(encoding="utf-8")
        cxrl = (ROOT / "android-client/test19r2/build.gradle.kts").read_text(encoding="utf-8")
        prepare = (ROOT / "scripts/tests/prepare_test19_r2.sh").read_text(encoding="utf-8")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertNotIn('?: throw GradleException("Pass -ProkidCxrVersion', cxrm)
        self.assertNotIn('?: throw GradleException("Pass -ProkidCxrLVersion', cxrl)
        self.assertIn("gradle.taskGraph.whenReady", cxrm)
        self.assertIn("gradle.taskGraph.whenReady", cxrl)
        self.assertIn("task.project.path == modulePath", cxrm)
        self.assertIn("task.project.path == modulePath", cxrl)
        self.assertIn('implementation("com.rokid.cxr:client-m:$cxrVersion")', cxrm)
        self.assertIn('implementation("com.rokid.cxr:client-l:$cxrLVersion")', cxrl)
        self.assertIn('"-ProkidCxrLVersion=$CXR_L_VERSION"', prepare)
        self.assertNotIn("-ProkidCxrVersion=", prepare)
        self.assertIn("android-client/*/build/", gitignore)

    def test_governed_prepare_uses_cxrl_property_only_and_cleans_build_output(self) -> None:
        prepare_script = ROOT / "scripts/tests/prepare_test19_r2.sh"
        with tempfile.TemporaryDirectory() as temp_value:
            temp = Path(temp_value)
            repo = temp / "repo"
            (repo / ".git/info").mkdir(parents=True)
            (repo / "android-client/test19r2").mkdir(parents=True)
            (repo / "android-client").mkdir(exist_ok=True)
            (repo / "scripts/research/cxr").mkdir(parents=True)

            sdk = temp / "sdk"
            (sdk / "platforms/android-36").mkdir(parents=True)
            (sdk / "platforms/android-36/android.jar").write_bytes(b"synthetic")
            (sdk / "platform-tools").mkdir(parents=True)

            java_home = temp / "java"
            (java_home / "bin").mkdir(parents=True)
            for name in ("java", "javap"):
                tool = java_home / "bin" / name
                tool.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
                tool.chmod(0o755)

            adb = sdk / "platform-tools/adb"
            adb.write_text(
                "#!/usr/bin/env bash\n"
                "args=\"$*\"\n"
                "case \"$args\" in\n"
                "  *'get-state'*) echo device ;;\n"
                "  *'dumpsys package com.rokid.sprite.global.aiapp'*) echo 'versionName=G1.11.11.0727' ;;\n"
                "  *'dumpsys package org.aimindseye.rokid.cxrlqualification'*) echo 'versionName=2.3-test19-r2.3' ;;\n"
                "  *'pm path org.aimindseye.rokid.cxrlqualification'*) echo 'package:/data/app/test19r2/base.apk' ;;\n"
                "  *'pm clear org.aimindseye.rokid.cxrlqualification'*) echo Success ;;\n"
                "  *'install -r'*) echo Success ;;\n"
                "  *) exit 0 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            adb.chmod(0o755)

            resolver = temp / "resolver.py"
            resolver.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "out=Path(sys.argv[sys.argv.index('--output')+1])\n"
                "out.mkdir(parents=True, exist_ok=True)\n"
                "(out/'cxr-l-artifact-attestation.json').write_text('{}')\n"
                "print('TEST19_R2_CXR_L_MAVEN_RESOLUTION=PASS')\n"
                "print('TEST19_R2_CXR_L_API_SURFACE=PASS')\n",
                encoding="utf-8",
            )

            gradle_args = temp / "gradle-args.txt"
            gradlew = repo / "android-client/gradlew"
            gradlew.write_text(
                "#!/usr/bin/env bash\n"
                f"printf '%s\\n' \"$@\" > {gradle_args}\n"
                "mkdir -p test19r2/build/outputs/apk/debug\n"
                "mkdir -p test19r2/build/outputs/logs\n"
                "printf 'synthetic-apk' > test19r2/build/outputs/apk/debug/test19r2-debug.apk\n"
                "printf '{}' > test19r2/build/outputs/apk/debug/output-metadata.json\n"
                "printf 'manifest' > test19r2/build/outputs/logs/manifest-merger-debug-report.txt\n"
                "exit 0\n",
                encoding="utf-8",
            )
            gradlew.chmod(0o755)

            private_root = temp / "private"
            build_log = temp / "build.log"
            install_log = temp / "install.log"
            env = os.environ.copy()
            env.update({
                "ANDROID_HOME": str(sdk),
                "ANDROID_SDK_ROOT": str(sdk),
                "ADB": str(adb),
                "TEST19_JAVA_HOME": str(java_home),
                "TEST19_CXR_L_RESOLVER": str(resolver),
                "TEST19_GRADLEW": str(gradlew),
                "TEST19_PRIVATE_ROOT": str(private_root),
                "TEST19_BUILD_LOG": str(build_log),
                "TEST19_INSTALL_LOG": str(install_log),
            })
            completed = subprocess.run(
                [
                    "bash", str(prepare_script),
                    "--repo", str(repo),
                    "--phone", "SYNTHETIC",
                    "--sdk-version", "1.0.1",
                    "--expected-hi-rokid-version", "G1.11.11.0727",
                    "--reset-app-data",
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("TEST19_R2_PREPARE=PASS", completed.stdout)
            self.assertIn("TEST19_R2_PACKAGE_IDENTITY=PASS", completed.stdout)
            self.assertIn("TEST19_R2_BUILD_OUTPUT_CLEANUP=PASS", completed.stdout)
            args = gradle_args.read_text(encoding="utf-8")
            self.assertIn("-ProkidCxrLVersion=1.0.1", args)
            self.assertNotIn("-ProkidCxrVersion=", args)
            self.assertFalse((repo / "android-client/test19r2/build").exists())
            self.assertTrue((private_root / "governed-build/test19r2-debug.apk").is_file())
            self.assertTrue((private_root / "governed-build/SHA256SUMS-private.txt").is_file())


if __name__ == "__main__":
    unittest.main()
