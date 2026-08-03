#!/usr/bin/env python3
"""Test 21 r3.3.4.2.6.1.3 host-only callback Stub dispatch recovery.

This analyzer treats the accepted r3.3.4.2.6.1.2 sanitized summary as the
Proxy/Parcel source and independently exercises each compiled callback Stub's
onTransact method on a host JVM using minimal clean-room android.os stand-ins.
No phone, ADB, root, Magisk, Frida, ptrace, process memory, or network access is
used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

EXPECTED_SOURCE_ZIP_SHA256 = "366facf0b4e87e6f100c0a0c322cdf298a98d7a82a8f782add2b716f4cf2fa8b"
EXPECTED_AAR_SHA256 = "c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e"
EXPECTED_CLASSES_JAR_SHA256 = "d2e1e2c875eb0283b80dd053b5edfcabd97b351d2c83abbcaa7026317f0b39d3"
EXPECTED_COORDINATE = "com.rokid.cxr:client-l:1.0.1"
EXPECTED_SERVICE_PREREQUISITE = "r3.3.4.2.6.1.1_ACCEPTED_TWO_SOURCE_CLIENT_BINDER_ABI"
EXPECTED_COUNTS = {
    "expected_interface_count": 7,
    "interface_present_count": 7,
    "descriptor_exact_count": 7,
    "stub_interface_count": 7,
    "structural_proxy_interface_count": 7,
    "total_method_count": 21,
    "ontransact_method_count": 14,
    "proxy_transaction_method_count": 21,
    "two_source_agreement_count": 14,
    "transaction_mismatch_count": 0,
    "request_parcel_contract_count": 21,
    "reply_parcel_contract_count": 21,
    "parcel_contract_count": 21,
    "abi_ready_interface_count": 3,
}

SUMMARY_JSON_NAME = "test21-r3-3-4-2-6-1-2-summary.json"
TX_TSV_NAME = "test21-r3-3-4-2-6-1-2-callback-transaction-map.tsv"


class AnalysisError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if p.returncode != 0:
        raise AnalysisError(
            "command failed (rc=%d): %s\nstdout:\n%s\nstderr:\n%s"
            % (p.returncode, " ".join(cmd), p.stdout, p.stderr)
        )
    return p


def require_jdk() -> Dict[str, str]:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        raise AnalysisError("JDK is required: both javac and java must be on PATH")
    javac_v = subprocess.run([javac, "-version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip()
    java_v = subprocess.run([java, "-version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.splitlines()[0].strip()
    return {"javac": javac, "java": java, "javac_version": javac_v, "java_version": java_v}


def safe_zip_read(path: Path, member: str) -> bytes:
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if member not in names:
            raise AnalysisError(f"required ZIP member missing: {member}")
        info = zf.getinfo(member)
        if info.is_dir() or info.file_size > 8 * 1024 * 1024:
            raise AnalysisError(f"unsafe or unexpectedly large ZIP member: {member}")
        return zf.read(member)


def load_baseline(source_zip: Path, allow_fixture: bool) -> Tuple[dict, List[dict], str]:
    source_sha = sha256_file(source_zip)
    if not allow_fixture and source_sha != EXPECTED_SOURCE_ZIP_SHA256:
        raise AnalysisError(
            f"source r3.3.4.2.6.1.2 ZIP SHA-256 mismatch: expected {EXPECTED_SOURCE_ZIP_SHA256}, got {source_sha}"
        )
    summary = json.loads(safe_zip_read(source_zip, SUMMARY_JSON_NAME).decode("utf-8"))
    tx_text = safe_zip_read(source_zip, TX_TSV_NAME).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(tx_text), delimiter="\t"))

    if summary.get("input", {}).get("coordinate") != EXPECTED_COORDINATE:
        raise AnalysisError("baseline coordinate mismatch")
    if not allow_fixture and summary.get("input", {}).get("aar_sha256") != EXPECTED_AAR_SHA256:
        raise AnalysisError("baseline AAR SHA-256 mismatch")
    if not allow_fixture and summary.get("input", {}).get("classes_jar_sha256") != EXPECTED_CLASSES_JAR_SHA256:
        raise AnalysisError("baseline classes.jar SHA-256 mismatch")

    counts = summary.get("callback_summary", {})
    for key, expected in EXPECTED_COUNTS.items():
        actual = counts.get(key)
        if actual != expected:
            raise AnalysisError(f"baseline count mismatch for {key}: expected {expected}, got {actual}")

    clean_room = summary.get("clean_room", {})
    if clean_room.get("service_binder_abi_prerequisite") != EXPECTED_SERVICE_PREREQUISITE:
        raise AnalysisError("accepted r3.3.4.2.6.1.1 service Binder prerequisite is missing")
    if len(rows) != 21:
        raise AnalysisError(f"expected 21 transaction rows, got {len(rows)}")
    return summary, rows, source_sha


def aar_candidates(repo: Path) -> Iterable[Path]:
    home = Path.home()
    explicit_patterns = [
        repo / "**" / "client-l-1.0.1.aar",
        home / ".gradle" / "caches" / "modules-2" / "files-2.1" / "com.rokid.cxr" / "client-l" / "1.0.1" / "**" / "client-l-1.0.1.aar",
        home / ".m2" / "repository" / "com" / "rokid" / "cxr" / "client-l" / "1.0.1" / "client-l-1.0.1.aar",
    ]
    seen: set[Path] = set()
    for pattern in explicit_patterns:
        pattern_s = str(pattern)
        if "**" in pattern_s:
            prefix = pattern_s.split("**", 1)[0]
            root = Path(prefix)
            if root.exists():
                for p in root.rglob("client-l-1.0.1.aar"):
                    rp = p.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        yield rp
        else:
            p = Path(pattern)
            if p.exists():
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    yield rp


def locate_aar(repo: Path, explicit: Path | None, allow_fixture: bool) -> Path:
    candidates: List[Path] = []
    if explicit:
        candidates.append(explicit.expanduser().resolve())
    candidates.extend(aar_candidates(repo))
    if not candidates:
        raise AnalysisError("client-l:1.0.1 AAR not found; pass --aar /path/to/client-l-1.0.1.aar")
    if allow_fixture and explicit:
        return explicit.expanduser().resolve()
    for candidate in candidates:
        if candidate.is_file() and sha256_file(candidate) == EXPECTED_AAR_SHA256:
            return candidate
    hashes = []
    for c in candidates[:12]:
        try:
            hashes.append(f"{c.name}:{sha256_file(c)}")
        except OSError:
            pass
    raise AnalysisError("no discovered AAR matched the accepted SHA-256; candidates=" + ",".join(hashes))


def extract_classes_jar(aar: Path, dest: Path, allow_fixture: bool) -> str:
    with zipfile.ZipFile(aar) as zf:
        if "classes.jar" not in zf.namelist():
            raise AnalysisError("AAR has no classes.jar")
        data = zf.read("classes.jar")
    classes_sha = sha256_bytes(data)
    if not allow_fixture and classes_sha != EXPECTED_CLASSES_JAR_SHA256:
        raise AnalysisError(
            f"classes.jar SHA-256 mismatch: expected {EXPECTED_CLASSES_JAR_SHA256}, got {classes_sha}"
        )
    dest.write_bytes(data)
    return classes_sha


def descriptor_args(proto: str) -> Tuple[List[str], str]:
    if not proto.startswith("("):
        raise AnalysisError(f"bad JVM method descriptor: {proto}")
    i = 1
    args: List[str] = []

    def parse_type(pos: int) -> Tuple[str, int]:
        array_depth = 0
        while proto[pos] == "[":
            array_depth += 1
            pos += 1
        ch = proto[pos]
        primitive = {
            "B": "byte", "C": "char", "D": "double", "F": "float", "I": "int",
            "J": "long", "S": "short", "Z": "boolean", "V": "void",
        }
        if ch in primitive:
            typ = primitive[ch]
            pos += 1
        elif ch == "L":
            end = proto.index(";", pos)
            typ = proto[pos + 1:end].replace("/", ".")
            pos = end + 1
        else:
            raise AnalysisError(f"unsupported JVM type in {proto} at {pos}")
        typ += "[]" * array_depth
        return typ, pos

    while proto[i] != ")":
        typ, i = parse_type(i)
        args.append(typ)
    ret, end = parse_type(i + 1)
    if end != len(proto):
        raise AnalysisError(f"trailing JVM descriptor data: {proto}")
    return args, ret


def java_literal(s: str) -> str:
    return json.dumps(s)


def write_android_mocks(root: Path) -> List[Path]:
    osdir = root / "android" / "os"
    osdir.mkdir(parents=True, exist_ok=True)
    files: Dict[str, str] = {
        "RemoteException.java": """
            package android.os;
            public class RemoteException extends Exception {
              public RemoteException() { super(); }
              public RemoteException(String s) { super(s); }
            }
        """,
        "IInterface.java": """
            package android.os;
            public interface IInterface { IBinder asBinder(); }
        """,
        "IBinder.java": """
            package android.os;
            public interface IBinder {
              int FIRST_CALL_TRANSACTION = 1;
              int LAST_CALL_TRANSACTION = 0x00ffffff;
              int INTERFACE_TRANSACTION = 0x5f4e5446;
              IInterface queryLocalInterface(String descriptor);
              boolean transact(int code, Parcel data, Parcel reply, int flags) throws RemoteException;
            }
        """,
        "Binder.java": """
            package android.os;
            public class Binder implements IBinder {
              private IInterface owner;
              private String descriptor;
              public Binder() {}
              public void attachInterface(IInterface owner, String descriptor) { this.owner = owner; this.descriptor = descriptor; }
              public IInterface queryLocalInterface(String descriptor) {
                return this.descriptor != null && this.descriptor.equals(descriptor) ? owner : null;
              }
              public boolean transact(int code, Parcel data, Parcel reply, int flags) throws RemoteException {
                return onTransact(code, data, reply, flags);
              }
              public boolean onTransact(int code, Parcel data, Parcel reply, int flags) throws RemoteException { return false; }
              public IBinder asBinder() { return this; }
            }
        """,
        "Parcel.java": """
            package android.os;
            import java.util.ArrayDeque;
            import java.util.Deque;
            public class Parcel {
              private final Deque<Object> q = new ArrayDeque<Object>();
              public static Parcel obtain() { return new Parcel(); }
              public static Parcel obtain(IBinder ignored) { return new Parcel(); }
              public void recycle() {}
              public void writeInterfaceToken(String s) { if (s != null) q.addLast(s); }
              public void enforceInterface(String s) {}
              public void enforceNoDataAvail() {}
              public void writeNoException() {}
              public void readException() {}
              public void writeInt(int v) { q.addLast(Integer.valueOf(v)); }
              public int readInt() { Object v = q.pollFirst(); return v instanceof Integer ? ((Integer)v).intValue() : 0; }
              public void writeBoolean(boolean v) { q.addLast(Boolean.valueOf(v)); }
              public boolean readBoolean() { Object v = q.pollFirst(); return v instanceof Boolean ? ((Boolean)v).booleanValue() : false; }
              public void writeString(String s) { if (s != null) q.addLast(s); }
              public String readString() { Object v = q.pollFirst(); return v instanceof String ? (String)v : null; }
              public void writeByteArray(byte[] b) { if (b != null) q.addLast(b); }
              public byte[] createByteArray() { Object v = q.pollFirst(); return v instanceof byte[] ? (byte[])v : new byte[0]; }
              public void writeStrongBinder(IBinder b) { if (b != null) q.addLast(b); }
              public IBinder readStrongBinder() { Object v = q.pollFirst(); return v instanceof IBinder ? (IBinder)v : null; }
            }
        """,
    }
    out: List[Path] = []
    for name, text in files.items():
        p = osdir / name
        p.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")
        out.append(p)
    return out


@dataclass
class Callback:
    label: str
    descriptor: str
    interface: str
    stub_class: str
    methods: List[dict]


def callbacks_from_summary(summary: dict) -> List[Callback]:
    result: List[Callback] = []
    for cb in summary.get("callbacks", []):
        methods = []
        for m in cb.get("methods", []):
            methods.append({"name": m["name"], "proto": m["proto"], "signature": m["signature"]})
        result.append(
            Callback(
                label=cb["label"],
                descriptor=cb["descriptor"],
                interface=cb["interface"].replace("/", "."),
                stub_class=cb["stub_class"].replace("/", "."),
                methods=methods,
            )
        )
    if len(result) != 7 or sum(len(c.methods) for c in result) != 21:
        raise AnalysisError("callback inventory is not the accepted 7-interface / 21-method set")
    return result


def write_probe_source(root: Path, cb: Callback, max_code: int) -> Path:
    pdir = root / "probe"
    pdir.mkdir(parents=True, exist_ok=True)
    cls = "Probe_" + re.sub(r"[^A-Za-z0-9_]", "_", cb.label)
    lines = [
        "package probe;",
        f"public final class {cls} extends {cb.stub_class.replace(chr(36), chr(46))} {{",
        "  private String last = \"\";",
        "  public void resetProbe() { last = \"\"; }",
        "  public String lastProbe() { return last; }",
    ]
    for m in cb.methods:
        args, ret = descriptor_args(m["proto"])
        if ret != "void":
            raise AnalysisError(f"callback method is unexpectedly non-void: {m['signature']}")
        decl = ", ".join(f"{typ} a{i}" for i, typ in enumerate(args))
        lines.extend([
            "  @Override",
            f"  public void {m['name']}({decl}) {{ last = {java_literal(m['signature'])}; }}",
        ])
    lines.extend([
        "  public static void main(String[] args) throws Exception {",
        f"    {cls} p = new {cls}();",
        f"    for (int code = 1; code <= {max_code}; code++) {{",
        "      p.resetProbe();",
        "      android.os.Parcel data = android.os.Parcel.obtain();",
        "      android.os.Parcel reply = android.os.Parcel.obtain();",
        "      boolean handled = p.onTransact(code, data, reply, 0);",
        f"      System.out.println(\"MAP\\t{cb.label}\\t\" + code + \"\\t\" + p.lastProbe() + \"\\t\" + handled);",
        "    }",
        "  }",
        "}",
    ])
    path = pdir / f"{cls}.java"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def recover_dispatch(classes_jar: Path, callbacks: List[Callback], tx_rows: List[dict], jdk: Dict[str, str], work: Path) -> Dict[Tuple[str, int], dict]:
    mock_src = work / "mock-src"
    mock_classes = work / "mock-classes"
    probe_src = work / "probe-src"
    probe_classes = work / "probe-classes"
    mock_classes.mkdir(parents=True)
    probe_classes.mkdir(parents=True)

    mock_files = write_android_mocks(mock_src)
    run([jdk["javac"], "--release", "8", "-d", str(mock_classes), *map(str, mock_files)])

    rows_by_label: Dict[str, List[dict]] = {}
    for row in tx_rows:
        rows_by_label.setdefault(row["callback_label"], []).append(row)

    probe_files: List[Path] = []
    max_by_label: Dict[str, int] = {}
    for cb in callbacks:
        proxy_codes = [int(r["proxy_code"]) for r in rows_by_label[cb.label] if r.get("proxy_code")]
        if not proxy_codes:
            raise AnalysisError(f"no Proxy codes for callback {cb.label}")
        max_by_label[cb.label] = max(proxy_codes)
        probe_files.append(write_probe_source(probe_src, cb, max_by_label[cb.label]))

    cp_compile = os.pathsep.join([str(mock_classes), str(classes_jar)])
    run([
        jdk["javac"], "--release", "8", "-cp", cp_compile,
        "-d", str(probe_classes), *map(str, probe_files)
    ])

    cp_run = os.pathsep.join([str(mock_classes), str(probe_classes), str(classes_jar)])
    observed: Dict[Tuple[str, int], dict] = {}
    for cb in callbacks:
        cls = "probe.Probe_" + re.sub(r"[^A-Za-z0-9_]", "_", cb.label)
        out = run([jdk["java"], "-cp", cp_run, cls]).stdout
        for raw in out.splitlines():
            if not raw.startswith("MAP\t"):
                continue
            parts = raw.split("\t")
            if len(parts) != 5:
                raise AnalysisError(f"malformed probe output: {raw}")
            _, label, code_s, signature, handled_s = parts
            key = (label, int(code_s))
            observed[key] = {
                "label": label,
                "code": int(code_s),
                "signature": signature,
                "handled": handled_s.lower() == "true",
            }
    return observed


def merge_and_validate(summary: dict, tx_rows: List[dict], observed: Dict[Tuple[str, int], dict]) -> Tuple[List[dict], Dict[str, dict]]:
    merged: List[dict] = []
    by_interface: Dict[str, dict] = {}
    seen_method_keys: set[Tuple[str, str]] = set()
    for row in tx_rows:
        label = row["callback_label"]
        proxy_code = int(row["proxy_code"])
        expected_sig = row["method_name"] + row["proto"]
        obs = observed.get((label, proxy_code))
        observed_sig = obs["signature"] if obs else ""
        handled = bool(obs and obs["handled"])
        agreement = handled and observed_sig == expected_sig
        mismatch = handled and bool(observed_sig) and observed_sig != expected_sig
        merged_row = dict(row)
        merged_row.update({
            "host_stub_code": str(proxy_code) if agreement else "",
            "host_stub_signature": observed_sig,
            "host_stub_handled": "YES" if handled else "NO",
            "host_stub_proxy_agreement": "YES" if agreement else "NO",
            "host_stub_mismatch": "YES" if mismatch else "NO",
            "merged_two_source_agreement": "YES" if agreement else "NO",
        })
        merged.append(merged_row)
        seen_method_keys.add((label, expected_sig))
        ent = by_interface.setdefault(label, {"methods": 0, "agreements": 0, "mismatches": 0})
        ent["methods"] += 1
        ent["agreements"] += int(agreement)
        ent["mismatches"] += int(mismatch)

    if len(merged) != 21 or len(seen_method_keys) != 21:
        raise AnalysisError("merged callback method set is not exactly 21 unique methods")
    return merged, by_interface


def write_outputs(
    out: Path,
    source_sha: str,
    aar_sha: str,
    classes_sha: str,
    jdk: Dict[str, str],
    baseline: dict,
    merged: List[dict],
    by_interface: Dict[str, dict],
    fixture_mode: bool,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    agreements = sum(1 for r in merged if r["merged_two_source_agreement"] == "YES")
    mismatches = sum(1 for r in merged if r["host_stub_mismatch"] == "YES")
    handled = sum(1 for r in merged if r["host_stub_handled"] == "YES")
    ready_interfaces = sum(1 for v in by_interface.values() if v["agreements"] == v["methods"] and v["mismatches"] == 0)
    missing_before = [r for r in merged if not r.get("ontransact_code")]
    missing_confirmed = sum(1 for r in missing_before if r["merged_two_source_agreement"] == "YES")

    closure = (
        not fixture_mode
        and agreements == 21
        and mismatches == 0
        and handled == 21
        and ready_interfaces == 7
        and missing_confirmed == 7
        and baseline["callback_summary"]["proxy_transaction_method_count"] == 21
        and baseline["callback_summary"]["parcel_contract_count"] == 21
        and baseline["clean_room"]["service_binder_abi_prerequisite"] == EXPECTED_SERVICE_PREREQUISITE
    )

    result = {
        "schema": "rokid.test21.r3.3.4.2.6.1.3.callback-stub-dispatch.v1",
        "analysis": "PASS" if agreements == 21 and mismatches == 0 else "INCOMPLETE",
        "access_mode": "HOST_ONLY_LOCAL_AAR_HOST_JVM",
        "fixture_mode": fixture_mode,
        "input": {
            "source_r3_3_4_2_6_1_2_zip_sha256": source_sha,
            "coordinate": baseline["input"]["coordinate"],
            "aar_sha256": aar_sha,
            "classes_jar_sha256": classes_sha,
            "service_binder_abi_prerequisite": baseline["clean_room"]["service_binder_abi_prerequisite"],
        },
        "host_jvm": {
            "javac_version": jdk["javac_version"],
            "java_version": jdk["java_version"],
            "android_os_standins": "MINIMAL_CLEAN_ROOM_NO_DEVICE",
        },
        "callback_summary": {
            "interface_count": 7,
            "method_count": 21,
            "baseline_ontransact_confirmation_count": 14,
            "baseline_two_source_agreement_count": 14,
            "host_stub_dispatch_handled_count": handled,
            "host_stub_dispatch_confirmation_count": agreements,
            "seven_missing_confirmation_count": missing_confirmed,
            "proxy_transaction_method_count": 21,
            "request_parcel_contract_count": 21,
            "reply_parcel_contract_count": 21,
            "parcel_contract_count": 21,
            "merged_two_source_agreement_count": agreements,
            "transaction_mismatch_count": mismatches,
            "abi_ready_interface_count": ready_interfaces,
            "all_callback_binder_abis_ready": closure,
            "callback_binder_boundary_ready": closure,
            "clean_room_full_binder_boundary_ready": closure,
        },
        "interfaces": [
            {
                "label": label,
                "method_count": v["methods"],
                "host_stub_proxy_agreement_count": v["agreements"],
                "mismatch_count": v["mismatches"],
                "abi_ready": closure and v["agreements"] == v["methods"] and v["mismatches"] == 0,
            }
            for label, v in sorted(by_interface.items())
        ],
        "methods": [
            {
                "callback_label": r["callback_label"],
                "descriptor": r["descriptor"],
                "transaction_code": int(r["proxy_code"]),
                "method_name": r["method_name"],
                "proto": r["proto"],
                "baseline_ontransact_code": int(r["ontransact_code"]) if r.get("ontransact_code") else None,
                "host_stub_code": int(r["host_stub_code"]) if r.get("host_stub_code") else None,
                "host_stub_signature": r["host_stub_signature"],
                "host_stub_handled": r["host_stub_handled"] == "YES",
                "host_stub_proxy_agreement": r["host_stub_proxy_agreement"] == "YES",
                "parcel_contract": r["parcel_contract"] == "YES",
            }
            for r in merged
        ],
        "clean_room": {
            "callback_binder_boundary_ready": closure,
            "full_binder_boundary_ready": closure,
            "disposition": "FULL_STATIC_BINDER_BOUNDARY_CLOSED" if closure else "CALLBACK_STUB_DISPATCH_CLOSURE_INCOMPLETE",
            "functional_behavior_compatibility_proven": False,
            "authorization_semantics_recovered": False,
            "session_lifecycle_semantics_recovered": False,
            "service_implementation_recovered": False,
        },
        "root_required": False,
        "magisk_required": False,
        "adb_required": False,
        "frida_required": False,
        "phone_action": "NONE",
        "network_required": False,
        "device_operation": "NONE",
        "photo_operation": "NONE",
        "audio_operation": "NONE",
        "network_capture": "NONE",
    }

    (out / "test21-r3-3-4-2-6-1-3-summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fields = list(merged[0].keys())
    with (out / "test21-r3-3-4-2-6-1-3-callback-transaction-map.tsv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(merged)

    lines = [
        "TEST21_R3_3_4_2_6_1_3_ANALYSIS=" + result["analysis"],
        "ACCESS_MODE=HOST_ONLY_LOCAL_AAR_HOST_JVM",
        "ROOT_REQUIRED=NO",
        "MAGISK_REQUIRED=NO",
        "ADB_REQUIRED=NO",
        "FRIDA_REQUIRED=NO",
        "PHONE_ACTION=NONE",
        "NETWORK_REQUIRED=NO",
        f"AAR_COORDINATE={EXPECTED_COORDINATE}",
        f"AAR_SHA256={aar_sha}",
        f"AAR_IDENTITY={'PASS' if fixture_mode or aar_sha == EXPECTED_AAR_SHA256 else 'FAIL'}",
        "CALLBACK_INTERFACE_COUNT=7",
        "CALLBACK_METHOD_COUNT=21",
        "BASELINE_ONTRANSACT_METHOD_COUNT=14",
        f"HOST_STUB_DISPATCH_HANDLED_COUNT={handled}",
        f"HOST_STUB_DISPATCH_CONFIRMATION_COUNT={agreements}",
        f"SEVEN_MISSING_ONTRANSACT_CONFIRMATION_COUNT={missing_confirmed}",
        "CALLBACK_PROXY_TRANSACTION_METHOD_COUNT=21",
        f"CALLBACK_TWO_SOURCE_AGREEMENT_COUNT={agreements}",
        f"CALLBACK_TRANSACTION_MISMATCH_COUNT={mismatches}",
        "CALLBACK_REQUEST_PARCEL_CONTRACT_COUNT=21",
        "CALLBACK_REPLY_PARCEL_CONTRACT_COUNT=21",
        "CALLBACK_PARCEL_CONTRACT_COUNT=21",
        f"CALLBACK_ABI_READY_INTERFACE_COUNT={ready_interfaces}",
        f"ALL_CALLBACK_BINDER_ABIS_READY={'YES' if closure else 'NO'}",
        f"CALLBACK_BINDER_BOUNDARY_READY={'YES' if closure else 'NO'}",
        f"CLEAN_ROOM_FULL_BINDER_BOUNDARY_READY={'YES' if closure else 'NO'}",
        "FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN=NO",
        "AUTHORIZATION_SEMANTICS_RECOVERED=NO",
        "SESSION_LIFECYCLE_SEMANTICS_RECOVERED=NO",
        "SERVICE_IMPLEMENTATION_RECOVERED=NO",
        "CLEAN_ROOM_DISPOSITION=" + result["clean_room"]["disposition"],
        "DEVICE_OPERATION=NONE",
        "PHOTO_OPERATION=NONE",
        "AUDIO_OPERATION=NONE",
        "NETWORK_CAPTURE=NONE",
    ]
    (out / "test21-r3-3-4-2-6-1-3-summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    md = [
        "# Test 21 r3.3.4.2.6.1.3 — Callback Stub Dispatch Closure",
        "",
        f"- Analysis: **{result['analysis']}**",
        f"- Host Stub dispatch confirmations: **{agreements}/21**",
        f"- Previously missing Stub confirmations closed: **{missing_confirmed}/7**",
        f"- Stub ↔ Proxy mismatches: **{mismatches}**",
        f"- ABI-ready callback interfaces: **{ready_interfaces}/7**",
        f"- Full clean-room Binder boundary ready: **{'YES' if closure else 'NO'}**",
        "",
        "The independent Stub-side confirmation executes only the compiled AAR's Binder Stub dispatch on a host JVM using minimal clean-room `android.os` stand-ins. It does not access a phone or glasses.",
        "",
        "This closes the static Binder ABI boundary only. It does not prove authorization semantics, session lifecycle, proprietary service implementation, or end-to-end functional compatibility.",
    ]
    (out / "test21-r3-3-4-2-6-1-3-summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--source-summary-zip", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--aar", type=Path)
    ap.add_argument("--fixture-mode", action="store_true", help=argparse.SUPPRESS)
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    allow_fixture = bool(args.fixture_mode and os.environ.get("TEST21_R613_ALLOW_FIXTURE") == "1")
    if args.fixture_mode and not allow_fixture:
        raise AnalysisError("fixture mode is test-only and requires TEST21_R613_ALLOW_FIXTURE=1")
    repo = args.repo.expanduser().resolve()
    source_zip = args.source_summary_zip.expanduser().resolve()
    out = args.output.expanduser().resolve()
    if not repo.is_dir():
        raise AnalysisError(f"repository directory not found: {repo}")
    if not source_zip.is_file():
        raise AnalysisError(f"source summary ZIP not found: {source_zip}")
    jdk = require_jdk()
    baseline, tx_rows, source_sha = load_baseline(source_zip, allow_fixture)
    callbacks = callbacks_from_summary(baseline)
    aar = locate_aar(repo, args.aar, allow_fixture)
    aar_sha = sha256_file(aar)
    if not allow_fixture and aar_sha != EXPECTED_AAR_SHA256:
        raise AnalysisError("AAR identity mismatch")

    with tempfile.TemporaryDirectory(prefix="test21-r613-") as td:
        work = Path(td)
        classes_jar = work / "classes.jar"
        classes_sha = extract_classes_jar(aar, classes_jar, allow_fixture)
        observed = recover_dispatch(classes_jar, callbacks, tx_rows, jdk, work)
        merged, by_interface = merge_and_validate(baseline, tx_rows, observed)

    if out.exists():
        shutil.rmtree(out)
    write_outputs(out, source_sha, aar_sha, classes_sha, jdk, baseline, merged, by_interface, allow_fixture)
    summary = json.loads((out / "test21-r3-3-4-2-6-1-3-summary.json").read_text(encoding="utf-8"))
    print((out / "test21-r3-3-4-2-6-1-3-summary.txt").read_text(encoding="utf-8"), end="")
    return 0 if summary["analysis"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AnalysisError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
