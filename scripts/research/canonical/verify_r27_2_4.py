#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from pcap_parser import get_profile
    from primitives import sha256_file
except ImportError:
    from scripts.research.canonical.pcap_parser import get_profile
    from scripts.research.canonical.primitives import sha256_file

TARGET = "com.rokid.sprite.global.aiapp"
OTHER = "com.example.other"
OUTPUT_FILES = (
    "network-packets-private.jsonl",
    "decrypted-http-private.jsonl",
    "network-parse-private.json",
)


def write_tsv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def ip4(text: str) -> bytes:
    return bytes(int(x) for x in text.split("."))


def tcp_packet(src: str, dst: str, src_port: int, dst_port: int, payload: bytes) -> bytes:
    total = 20 + 20 + len(payload)
    ip = bytearray(20)
    ip[0] = 0x45
    struct.pack_into("!H", ip, 2, total)
    ip[8] = 64
    ip[9] = 6
    ip[12:16] = ip4(src)
    ip[16:20] = ip4(dst)
    tcp = bytearray(20)
    struct.pack_into("!HH", tcp, 0, src_port, dst_port)
    tcp[12] = 0x50
    return bytes(ip + tcp + payload)


def dns_query(name: str) -> bytes:
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    labels = b"".join(bytes([len(part)]) + part.encode("ascii") for part in name.split(".")) + b"\0"
    return header + labels + struct.pack("!HH", 1, 1)


def udp_packet(src: str, dst: str, src_port: int, dst_port: int, payload: bytes) -> bytes:
    total = 20 + 8 + len(payload)
    ip = bytearray(20)
    ip[0] = 0x45
    struct.pack_into("!H", ip, 2, total)
    ip[8] = 64
    ip[9] = 17
    ip[12:16] = ip4(src)
    ip[16:20] = ip4(dst)
    udp = bytearray(8)
    struct.pack_into("!HHHH", udp, 0, src_port, dst_port, 8 + len(payload), 0)
    return bytes(ip + udp + payload)


def trailer(uid: int, name: str) -> bytes:
    raw_name = name.encode("utf-8")[:20].ljust(20, b"\0")
    return struct.pack("<Ii", 0x01072021, uid) + raw_name


def ethernet(payload: bytes) -> bytes:
    return b"\x02\x00\x00\x00\x00\x01" + b"\x02\x00\x00\x00\x00\x02" + b"\x08\x00" + payload


def make_pcap(path: Path, *, linktype: int, raw_frames: bool = False) -> None:
    http = (
        b"GET /api/0123456789abcdef0123456789abcdef?token=secret HTTP/1.1\r\n"
        b"Host: api.example.com\r\nUser-Agent: r2724\r\n\r\n"
    )
    packet1 = tcp_packet("10.0.0.2", "8.8.8.8", 12345, 443, http) + trailer(12345, "sprite")
    packet2 = udp_packet("10.0.0.2", "8.8.4.4", 53000, 53, dns_query("dns.example.com")) + trailer(12346, "other")
    frames = [packet1, packet2] if raw_frames else [ethernet(packet1), ethernet(packet2)]
    blob = bytearray(b"\xd4\xc3\xb2\xa1")
    blob += struct.pack("<HHIIII", 2, 4, 0, 0, 65535, linktype)
    for idx, frame in enumerate(frames):
        sec = 1700000000 + idx
        usec = 123456 + idx
        blob += struct.pack("<IIII", sec, usec, len(frame), len(frame))
        blob += frame
    path.write_bytes(blob)


def make_fake_tshark(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3\n"
        "import sys\n"
        "args=sys.argv[1:]\n"
        "fields=[]\n"
        "i=0\n"
        "while i < len(args):\n"
        "    if args[i]=='-e' and i+1 < len(args): fields.append(args[i+1]); i+=2\n"
        "    else: i+=1\n"
        "values={\n"
        " 'frame.number':'1', 'frame.time_epoch':'1700000000.123456',\n"
        " 'ip.src':'10.0.0.2', 'ipv6.src':'', 'ip.dst':'8.8.8.8', 'ipv6.dst':'',\n"
        " 'tcp.srcport':'12345', 'tcp.dstport':'443', 'http.request.method':'GET',\n"
        " 'http.host':'api.example.com',\n"
        " 'http.request.uri':'/api/0123456789abcdef0123456789abcdef?token=secret',\n"
        " 'http.response.code':'', 'http2.headers.method':'', 'http2.headers.authority':'',\n"
        " 'http2.headers.path':'', 'http2.headers.status':''\n"
        "}\n"
        "print('\\t'.join(values.get(f,'') for f in fields))\n"
        """,
        encoding="utf-8",
    )
    path.chmod(0o755)


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=90)


def compare_files(a: Path, b: Path) -> tuple[bool, str]:
    for name in OUTPUT_FILES:
        pa, pb = a / name, b / name
        if not pa.is_file() or not pb.is_file():
            return False, f"missing:{name}"
        if pa.read_bytes() != pb.read_bytes():
            return False, f"bytes:{name}"
    return True, ""


def primary_case(repo: Path, revision: str, root: Path) -> dict:
    legacy_out = root / "legacy-primary"
    canonical_out = root / "canonical-primary"
    legacy_out.mkdir(parents=True)
    canonical_out.mkdir(parents=True)
    pcap = root / "ethernet.pcap"
    uid_map = root / "uid-map.json"
    keylog = root / "sslkeylog.txt"
    fake_bin = root / "bin"
    fake_bin.mkdir()
    make_pcap(pcap, linktype=1, raw_frames=False)
    uid_map.write_text(json.dumps({"12345": TARGET, "12346": OTHER}, sort_keys=True) + "\n", encoding="utf-8")
    keylog.write_text("CLIENT_RANDOM 00 00\n", encoding="utf-8")
    make_fake_tshark(fake_bin / "tshark")
    env = os.environ.copy()
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    legacy = get_profile(revision)["legacy_path"]
    old = run(
        [sys.executable, legacy, "--pcap", str(pcap), "--uid-map", str(uid_map), "--output", str(legacy_out), "--sslkeylog", str(keylog)],
        cwd=repo,
        env=env,
    )
    new = run(
        [str(repo / "scripts/rokid-research"), "network", "parse-pcap", "--revision", revision, "--pcap", str(pcap), "--uid-map", str(uid_map), "--output", str(canonical_out), "--sslkeylog", str(keylog)],
        cwd=repo,
        env=env,
    )
    files_equal, detail = compare_files(legacy_out, canonical_out)
    return {
        "revision": revision,
        "case": "ethernet_fake_tshark",
        "legacy_rc": old.returncode,
        "canonical_rc": new.returncode,
        "stdout_equal": "YES" if old.stdout == new.stdout else "NO",
        "output_files_equal": "YES" if files_equal else "NO",
        "detail": detail,
        "equivalent": "YES" if old.returncode == 0 and new.returncode == 0 and old.stdout == new.stdout and files_equal else "NO",
    }


def short_header_case(repo: Path, revision: str, root: Path) -> dict:
    legacy_out = root / "legacy-short"
    canonical_out = root / "canonical-short"
    legacy_out.mkdir(parents=True)
    canonical_out.mkdir(parents=True)
    pcap = root / "short.pcap"
    uid_map = root / "uid-map-short.json"
    pcap.write_bytes(b"short")
    uid_map.write_text("{}\n", encoding="utf-8")
    legacy = get_profile(revision)["legacy_path"]
    old = run([sys.executable, legacy, "--pcap", str(pcap), "--uid-map", str(uid_map), "--output", str(legacy_out)], cwd=repo)
    new = run([str(repo / "scripts/rokid-research"), "network", "parse-pcap", "--revision", revision, "--pcap", str(pcap), "--uid-map", str(uid_map), "--output", str(canonical_out)], cwd=repo)
    files_equal, detail = compare_files(legacy_out, canonical_out)
    return {
        "revision": revision,
        "case": "short_header",
        "legacy_rc": old.returncode,
        "canonical_rc": new.returncode,
        "stdout_equal": "YES" if old.stdout == new.stdout else "NO",
        "output_files_equal": "YES" if files_equal else "NO",
        "detail": detail,
        "equivalent": "YES" if old.returncode == 0 and new.returncode == 0 and old.stdout == new.stdout and files_equal else "NO",
    }


def raw_linktype_case(repo: Path, root: Path) -> dict:
    revision = "r3.3.3.1"
    legacy_out = root / "legacy-raw"
    canonical_out = root / "canonical-raw"
    legacy_out.mkdir(parents=True)
    canonical_out.mkdir(parents=True)
    pcap = root / "raw.pcap"
    uid_map = root / "uid-map-raw.json"
    make_pcap(pcap, linktype=101, raw_frames=True)
    uid_map.write_text(json.dumps({"12345": TARGET, "12346": OTHER}, sort_keys=True) + "\n", encoding="utf-8")
    legacy = get_profile(revision)["legacy_path"]
    old = run([sys.executable, legacy, "--pcap", str(pcap), "--uid-map", str(uid_map), "--output", str(legacy_out)], cwd=repo)
    new = run([str(repo / "scripts/rokid-research"), "network", "parse-pcap", "--revision", revision, "--pcap", str(pcap), "--uid-map", str(uid_map), "--output", str(canonical_out)], cwd=repo)
    files_equal, detail = compare_files(legacy_out, canonical_out)
    return {
        "revision": revision,
        "case": "raw_linktype_101",
        "legacy_rc": old.returncode,
        "canonical_rc": new.returncode,
        "stdout_equal": "YES" if old.stdout == new.stdout else "NO",
        "output_files_equal": "YES" if files_equal else "NO",
        "detail": detail,
        "equivalent": "YES" if old.returncode == 0 and new.returncode == 0 and old.stdout == new.stdout and files_equal else "NO",
    }


def negative_case(repo: Path, revision: str, root: Path) -> dict:
    legacy_out = root / "legacy-bad"
    canonical_out = root / "canonical-bad"
    legacy_out.mkdir(parents=True)
    canonical_out.mkdir(parents=True)
    pcap = root / "bad.pcap"
    uid_map = root / "uid-map-bad.json"
    pcap.write_bytes(b"X" * 24)
    uid_map.write_text("{}\n", encoding="utf-8")
    legacy = get_profile(revision)["legacy_path"]
    old = run([sys.executable, legacy, "--pcap", str(pcap), "--uid-map", str(uid_map), "--output", str(legacy_out)], cwd=repo)
    new = run([str(repo / "scripts/rokid-research"), "network", "parse-pcap", "--revision", revision, "--pcap", str(pcap), "--uid-map", str(uid_map), "--output", str(canonical_out)], cwd=repo)
    old_marker = "unsupported PCAP magic" in old.stderr
    new_marker = "unsupported PCAP magic" in new.stderr
    return {
        "revision": revision,
        "case": "unsupported_magic",
        "legacy_rc": old.returncode,
        "canonical_rc": new.returncode,
        "legacy_rejected": "YES" if old.returncode != 0 and old_marker else "NO",
        "canonical_rejected": "YES" if new.returncode != 0 and new_marker else "NO",
        "equivalent": "YES" if old.returncode != 0 and new.returncode != 0 and old_marker and new_marker else "NO",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    out = Path(args.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    revisions = ["r3.3.3", "r3.3.3.1"]

    source_rows: list[dict] = []
    source_failures = 0
    for revision in revisions:
        p = get_profile(revision)
        source = repo / p["legacy_path"]
        actual = sha256_file(source) if source.is_file() else ""
        ok = actual == p["legacy_sha256"]
        source_failures += 0 if ok else 1
        source_rows.append({
            "revision": revision,
            "legacy_path": p["legacy_path"],
            "expected_sha256": p["legacy_sha256"],
            "actual_sha256": actual,
            "source_lock": "PASS" if ok else "FAIL",
        })
    write_tsv(out / "source-locks.tsv", source_rows, ["revision", "legacy_path", "expected_sha256", "actual_sha256", "source_lock"])
    if source_failures:
        print("R27_2_4_EQUIVALENCE=FAIL")
        print(f"LEGACY_SOURCE_LOCK_FAILURE_COUNT={source_failures}")
        return 1

    positive_rows: list[dict] = []
    negative_rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="r2724-equivalence-") as tmp:
        root = Path(tmp)
        for revision in revisions:
            case_root = root / revision.replace(".", "_")
            case_root.mkdir()
            positive_rows.append(primary_case(repo, revision, case_root))
            positive_rows.append(short_header_case(repo, revision, case_root))
            negative_rows.append(negative_case(repo, revision, case_root))
        raw_root = root / "raw_linktype"
        raw_root.mkdir()
        positive_rows.append(raw_linktype_case(repo, raw_root))

    positive_fields = ["revision", "case", "legacy_rc", "canonical_rc", "stdout_equal", "output_files_equal", "detail", "equivalent"]
    negative_fields = ["revision", "case", "legacy_rc", "canonical_rc", "legacy_rejected", "canonical_rejected", "equivalent"]
    write_tsv(out / "parser-equivalence.tsv", positive_rows, positive_fields)
    write_tsv(out / "negative-equivalence.tsv", negative_rows, negative_fields)

    positive_failures = sum(row["equivalent"] != "YES" for row in positive_rows)
    negative_failures = sum(row["equivalent"] != "YES" for row in negative_rows)
    profile_equivalent = 0
    for revision in revisions:
        if all(row["equivalent"] == "YES" for row in positive_rows if row["revision"] == revision) and all(row["equivalent"] == "YES" for row in negative_rows if row["revision"] == revision):
            profile_equivalent += 1

    summary = {
        "schema": "rokid.r27.2.4.test21-pcap-parser-equivalence.v1",
        "status": "PASS" if profile_equivalent == 2 and not positive_failures and not negative_failures else "FAIL",
        "pcap_parser_profile_count": 2,
        "pcap_parser_equivalent_profile_count": profile_equivalent,
        "positive_equivalence_case_count": len(positive_rows),
        "positive_equivalence_failure_count": positive_failures,
        "negative_equivalence_case_count": len(negative_rows),
        "negative_equivalence_failure_count": negative_failures,
        "legacy_source_lock_failure_count": source_failures,
        "historical_file_action": "NONE",
        "repository_deletion": "NONE",
        "device_operation": "NONE",
        "privileged_operation": "NONE",
        "network_operation": "NONE",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("R27_2_4_EQUIVALENCE=" + summary["status"])
    print("PCAP_PARSER_PROFILE_COUNT=2")
    print(f"PCAP_PARSER_EQUIVALENT_PROFILE_COUNT={profile_equivalent}")
    print(f"POSITIVE_EQUIVALENCE_CASE_COUNT={len(positive_rows)}")
    print(f"NEGATIVE_EQUIVALENCE_CASE_COUNT={len(negative_rows)}")
    print(f"LEGACY_SOURCE_LOCK_FAILURE_COUNT={source_failures}")
    print("HISTORICAL_FILE_ACTION=NONE")
    print("REPOSITORY_DELETION=NONE")
    print("DEVICE_OPERATION=NONE")
    print("PRIVILEGED_OPERATION=NONE")
    print("NETWORK_OPERATION=NONE")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
