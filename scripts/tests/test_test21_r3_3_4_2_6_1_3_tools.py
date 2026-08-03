#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, shutil, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path

HERE = Path(__file__).resolve()
ANALYZER = HERE.parents[1] / "research" / "cxr" / "analyze_test21_r3_3_4_2_6_1_3_callback_stub_dispatch.py"
spec = importlib.util.spec_from_file_location("r613", ANALYZER)
r613 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r613
assert spec.loader
spec.loader.exec_module(r613)

PACKAGER = HERE.parents[1] / "research" / "cxr" / "package_test21_r3_3_4_2_6_1_3_sanitized.py"
pspec = importlib.util.spec_from_file_location("r613pack", PACKAGER)
r613pack = importlib.util.module_from_spec(pspec)
assert pspec.loader
pspec.loader.exec_module(r613pack)

CALLBACKS = [
    ("IMAGE", "IImageStreamCallback", [("onImageReceived", "([B)V"), ("onImageError", "(ILjava/lang/String;)V")]),
    ("AUDIO", "IAudioStreamCallback", [("onAudioReceived", "([BII)V"), ("onAudioError", "(ILjava/lang/String;)V"), ("onAudioStreamStateChanged", "(Z)V")]),
    ("CUSTOM_VIEW", "ICustomViewCallback", [("onCustomViewOpened", "()V"), ("onCustomViewUpdated", "()V"), ("onCustomViewClosed", "()V"), ("onCustomViewIconsSent", "()V"), ("onCustomViewError", "(ILjava/lang/String;)V")]),
    ("DEVICE_STATUS", "IDeviceStatusCallback", [("onDeviceConnectChanged", "(Z)V")]),
    ("CUSTOM_CMD", "ICustomCmdCallback", [("onCustomCmdResult", "(Ljava/lang/String;[B)V")]),
    ("GLASS_APP", "IGlassAppCallback", [("onInstallAppResult", "(Z)V"), ("onUnInstallAppResult", "(Z)V"), ("onOpenAppResult", "(Z)V"), ("onStopAppResult", "(Z)V"), ("onQueryAppResult", "(Ljava/lang/String;Z)V")]),
    ("AI_EVENT", "IAiEventCallback", [("onAiKeyDown", "()V"), ("onAiKeyUp", "()V"), ("onAiExit", "()V"), ("onGlassAppResumeChange", "(Ljava/lang/String;Ljava/lang/String;)V")]),
]

class Contract(unittest.TestCase):
    def test_fixed_identities(self):
        self.assertEqual(len(r613.EXPECTED_AAR_SHA256), 64)
        self.assertEqual(len(r613.EXPECTED_SOURCE_ZIP_SHA256), 64)
        self.assertEqual(r613.EXPECTED_COUNTS["total_method_count"], 21)
        self.assertEqual(r613.EXPECTED_COUNTS["ontransact_method_count"], 14)

    def test_descriptor_parser(self):
        self.assertEqual(r613.descriptor_args("([BII)V"), (["byte[]", "int", "int"], "void"))
        self.assertEqual(r613.descriptor_args("(Ljava/lang/String;Z)V"), (["java.lang.String", "boolean"], "void"))

    def test_runner_has_no_device_commands(self):
        runner = (ANALYZER.parent / "run_test21_r3_3_4_2_6_1_3.sh").read_text()
        for forbidden in [" adb ", "magisk", "frida", "/proc/", "ptrace"]:
            self.assertNotIn(forbidden, runner.lower())
        self.assertIn("TERMINAL_REMAINS_OPEN=YES", runner)

    def test_ipv4_gate_ignores_long_dotted_version(self):
        samples = [
            "# Test 21 r3.3.4.2.6.1.3 — Callback Stub Dispatch Closure",
            "rokid.test21.r3.3.4.2.6.1.3.callback-stub-dispatch.v1",
        ]
        for sample in samples:
            self.assertIsNone(r613pack.privacy_violation(sample), sample)

    def test_ipv4_gate_still_rejects_real_addresses(self):
        samples = [
            "peer=10.0.0.1",
            "address 192.168.68.68:443",
            "remote=255.255.255.255",
        ]
        for sample in samples:
            self.assertEqual(r613pack.privacy_violation(sample), "ipv4", sample)

class SyntheticDispatch(unittest.TestCase):
    @unittest.skipUnless(shutil.which("javac") and shutil.which("jar") and shutil.which("java"), "JDK required")
    def test_all_21_stub_routes(self):
        with tempfile.TemporaryDirectory(prefix="r613-unit-") as td:
            root = Path(td)
            mock_src = root / "mock-src"
            mock_classes = root / "mock-classes"
            mock_classes.mkdir()
            mock_files = r613.write_android_mocks(mock_src)
            subprocess.run([shutil.which("javac"), "--release", "8", "-d", str(mock_classes), *map(str,mock_files)], check=True)

            src = root / "src" / "com" / "rokid" / "sprite" / "aiapp" / "externalapp"
            src.mkdir(parents=True)
            callbacks=[]; tx_rows=[]
            for label, iface, methods in CALLBACKS:
                descriptor=f"com.rokid.sprite.aiapp.externalapp.{iface}"
                j=[]
                j.append("package com.rokid.sprite.aiapp.externalapp;")
                j.append(f"public interface {iface} extends android.os.IInterface {{")
                for name,proto in methods:
                    args,ret=r613.descriptor_args(proto)
                    decl=", ".join(f"{t} a{i}" for i,t in enumerate(args))
                    j.append(f"  {ret} {name}({decl}) throws android.os.RemoteException;")
                j.append(f"  abstract class Stub extends android.os.Binder implements {iface} {{")
                j.append(f"    public Stub() {{ attachInterface(this, \"{descriptor}\"); }}")
                j.append("    public android.os.IBinder asBinder() { return this; }")
                j.append("    public boolean onTransact(int code, android.os.Parcel data, android.os.Parcel reply, int flags) throws android.os.RemoteException {")
                j.append("      switch(code) {")
                for code,(name,proto) in enumerate(methods,1):
                    args,_=r613.descriptor_args(proto)
                    vals=[]
                    for t in args:
                        vals.append({"byte[]":"data.createByteArray()","int":"data.readInt()","boolean":"data.readInt()!=0","java.lang.String":"data.readString()"}[t])
                    j.append(f"        case {code}: data.enforceInterface(\"{descriptor}\"); {name}({', '.join(vals)}); reply.writeNoException(); return true;")
                    tx_rows.append({"callback_label":label,"descriptor":descriptor,"transaction_code":str(code),"method_name":name,"proto":proto,"ontransact_code":"" if label in {"IMAGE","AUDIO","DEVICE_STATUS","CUSTOM_CMD"} else str(code),"proxy_code":str(code),"two_source_agreement":"NO" if label in {"IMAGE","AUDIO","DEVICE_STATUS","CUSTOM_CMD"} else "YES","transact_flags":"0","reply_mode":"SYNC_REPLY","parcel_contract":"YES"})
                j.append("        default: return super.onTransact(code,data,reply,flags);")
                j.append("      }")
                j.append("    }")
                j.append("  }")
                j.append("}")
                (src/f"{iface}.java").write_text("\n".join(j)+"\n")
                callbacks.append(r613.Callback(label,descriptor,descriptor,descriptor+"$Stub",[{"name":n,"proto":p,"signature":n+p} for n,p in methods]))

            classes_dir=root/"classes"; classes_dir.mkdir()
            sources=list(src.glob("*.java"))
            cp=str(mock_classes)
            subprocess.run([shutil.which("javac"),"--release","8","-cp",cp,"-d",str(classes_dir),*map(str,sources)],check=True)
            classes_jar=root/"classes.jar"
            subprocess.run([shutil.which("jar"),"cf",str(classes_jar),"-C",str(classes_dir),"."],check=True)
            jdk=r613.require_jdk()
            observed=r613.recover_dispatch(classes_jar,callbacks,tx_rows,jdk,root/"probe-work")
            merged,by_iface=r613.merge_and_validate({},tx_rows,observed)
            self.assertEqual(sum(r["merged_two_source_agreement"]=="YES" for r in merged),21)
            self.assertEqual(sum(v["agreements"]==v["methods"] for v in by_iface.values()),7)

if __name__ == "__main__": unittest.main(verbosity=2)
