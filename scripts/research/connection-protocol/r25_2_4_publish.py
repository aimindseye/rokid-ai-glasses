#!/usr/bin/env python3
"""Validate accepted r25.2.3.2 evidence and publish final repository documentation."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

RELEASE = "r1.3.3.2.25.2.4"
EXPECTED_ACCEPTANCE = "PASS_FULL_RFCOMM_HCI_ZERO_PAYLOAD_CLOSURE"
EXPECTED_OUTCOME = "RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS"
README_BEGIN = "<!-- BEGIN R1.3.3.2.25.2.4 FINAL RFCOMM CLOSURE -->"
README_END = "<!-- END R1.3.3.2.25.2.4 FINAL RFCOMM CLOSURE -->"


class PublicationError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_zip_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    seen: set[str] = set()
    for info in infos:
        name = info.filename
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts or name.startswith("/"):
            raise PublicationError(f"unsafe ZIP member: {name}")
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise PublicationError(f"symlink ZIP member rejected: {name}")
        if name in seen:
            raise PublicationError(f"duplicate ZIP member rejected: {name}")
        seen.add(name)
    return infos


def read_zip(path: Path) -> tuple[zipfile.ZipFile, bytes]:
    data = path.read_bytes()
    bio = io.BytesIO(data)
    zf = zipfile.ZipFile(bio)
    safe_zip_members(zf)
    # Keep BytesIO alive through a private attribute.
    setattr(zf, "_source_bio", bio)
    return zf, data


def find_member(zf: zipfile.ZipFile, suffix: str) -> str:
    matches = [n for n in zf.namelist() if n.endswith(suffix)]
    if len(matches) != 1:
        raise PublicationError(f"expected exactly one ZIP member ending {suffix!r}; found {matches}")
    return matches[0]


def parse_manifest(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(.+)", line)
        if not match:
            raise PublicationError(f"invalid manifest line {line_no}: {raw!r}")
        rows.append((match.group(1), match.group(2)))
    if not rows:
        raise PublicationError("empty SHA-256 manifest")
    return rows


def verify_internal_manifest(zf: zipfile.ZipFile, manifest_suffix: str) -> tuple[str, int]:
    manifest_name = find_member(zf, manifest_suffix)
    manifest_dir = PurePosixPath(manifest_name).parent
    rows = parse_manifest(zf.read(manifest_name).decode("utf-8"))
    for expected, rel in rows:
        candidate = str(manifest_dir / rel)
        if candidate not in zf.namelist():
            raise PublicationError(f"manifest member missing: {candidate}")
        actual = sha256_bytes(zf.read(candidate))
        if actual != expected:
            raise PublicationError(f"manifest hash mismatch for {candidate}: {actual} != {expected}")
    return manifest_name, len(rows)


def json_member(zf: zipfile.ZipFile, suffix: str) -> dict[str, Any]:
    name = find_member(zf, suffix)
    try:
        value = json.loads(zf.read(name))
    except Exception as exc:
        raise PublicationError(f"invalid JSON member {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise PublicationError(f"JSON root must be an object: {name}")
    return value


def assert_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise PublicationError(f"{label}: {actual!r} != {expected!r}")


def assert_true(label: str, actual: Any) -> None:
    if actual is not True:
        raise PublicationError(f"{label}: expected true, got {actual!r}")


def assert_false(label: str, actual: Any) -> None:
    if actual is not False:
        raise PublicationError(f"{label}: expected false, got {actual!r}")


def extract_handoff_hash(evidence_zf: zipfile.ZipFile) -> str:
    name = find_member(evidence_zf, "strict-runner/runner-terminal-private.txt")
    text = evidence_zf.read(name).decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    match = re.search(r"^R25_2_2_2_SOURCE_HANDOFF_SHA256=([0-9a-f]{64})$", text, re.MULTILINE)
    if not match:
        raise PublicationError("strict source handoff SHA-256 not found")
    return match.group(1)


def verify_hci_member(evidence_zf: zipfile.ZipFile, summary: dict[str, Any]) -> tuple[str, str]:
    bugreport_name = find_member(evidence_zf, "private-evidence/bugreport.zip")
    bugreport_data = evidence_zf.read(bugreport_name)
    with zipfile.ZipFile(io.BytesIO(bugreport_data)) as inner:
        safe_zip_members(inner)
        member = str(summary["selected_hci_census"]["member"])
        if "!/" not in member:
            raise PublicationError(f"invalid nested HCI member identity: {member}")
        inner_suffix = member.split("!/", 1)[1]
        candidates = [n for n in inner.namelist() if n == inner_suffix or n.endswith("/" + inner_suffix)]
        if len(candidates) != 1:
            raise PublicationError(f"expected one nested HCI member {inner_suffix!r}; found {candidates}")
        data = inner.read(candidates[0])
        actual = sha256_bytes(data)
        expected = str(summary["selected_hci_census"]["member_sha256"])
        assert_equal("nested HCI member SHA-256", actual, expected)
        return candidates[0], actual


def scan_sanitized_input(zf: zipfile.ZipFile) -> None:
    forbidden_patterns = {
        "absolute macOS path": re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
        "full Bluetooth address": re.compile(rb"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])"),
        "serial assignment": re.compile(
            rb"""(?i)["']?(?:[a-z0-9]+[ _-]*)?serial(?:_number)?["']?\s*[:=]\s*["']?[a-z0-9._:-]{6,}"""
        ),
        "ADB command": re.compile(rb"(?i)\badb\s+-s\b"),
    }
    for info in zf.infolist():
        if info.is_dir() or info.file_size > 2_000_000:
            continue
        data = zf.read(info.filename)
        for label, pattern in forbidden_patterns.items():
            if pattern.search(data):
                raise PublicationError(f"sanitized input contains {label}: {info.filename}")


@dataclass(frozen=True)
class ValidatedInputs:
    sanitized_sha256: str
    analysis_sha256: str
    evidence_sha256: str
    source_private_sha256: str
    source_handoff_sha256: str
    hci_member_sha256: str
    hci_member_path: str
    frame_fingerprint_sha256: str
    strict_runner_sha256: str
    summary: dict[str, Any]
    private: dict[str, Any]
    manifest_counts: dict[str, int]


def validate_inputs(
    sanitized_path: Path,
    analysis_path: Path,
    evidence_path: Path,
    expected_sanitized_sha256: str,
    expected_analysis_sha256: str,
    expected_evidence_sha256: str,
) -> ValidatedInputs:
    for path in (sanitized_path, analysis_path, evidence_path):
        if not path.is_file():
            raise PublicationError(f"input archive not found: {path}")

    hashes = {
        "sanitized": sha256_file(sanitized_path),
        "analysis": sha256_file(analysis_path),
        "evidence": sha256_file(evidence_path),
    }
    assert_equal("sanitized publication ZIP SHA-256", hashes["sanitized"], expected_sanitized_sha256)
    assert_equal("private analysis ZIP SHA-256", hashes["analysis"], expected_analysis_sha256)
    assert_equal("private evidence ZIP SHA-256", hashes["evidence"], expected_evidence_sha256)

    sanitized_zf, _ = read_zip(sanitized_path)
    analysis_zf, _ = read_zip(analysis_path)
    evidence_zf, _ = read_zip(evidence_path)
    try:
        san_manifest, san_count = verify_internal_manifest(sanitized_zf, "publication/SHA256SUMS-sanitized.txt")
        ana_manifest, ana_count = verify_internal_manifest(analysis_zf, "private-analysis/SHA256SUMS-private-analysis.txt")
        ev_manifest, ev_count = verify_internal_manifest(evidence_zf, "private-evidence/SHA256SUMS-private.txt")
        scan_sanitized_input(sanitized_zf)

        summary = json_member(sanitized_zf, "publication/r25.2.3.2-runtime-status-summary.json")
        analysis_summary = json_member(analysis_zf, "private-analysis/publication/r25.2.3.2-runtime-status-summary.json")
        private = json_member(analysis_zf, "private-analysis/analysis/r25.2.3.2-private-analysis.json")

        assert_equal("sanitized/private publication summary", summary, analysis_summary)
        assert_equal("sanitized acceptance", summary.get("acceptance"), EXPECTED_ACCEPTANCE)
        assert_equal("private acceptance", private.get("acceptance"), EXPECTED_ACCEPTANCE)
        assert_equal("qualification outcome", summary.get("qualification_outcome"), EXPECTED_OUTCOME)
        assert_equal("private qualification outcome", private.get("qualification_outcome"), EXPECTED_OUTCOME)
        assert_equal("release", summary.get("release"), "r1.3.3.2.25.2.3.2")

        gates = summary.get("gates", {})
        assert_true("lifecycle closure", gates.get("lifecycle_closure_proven"))
        assert_true("HCI zero payload", gates.get("hci_zero_payload_proven"))
        assert_true("full closure", gates.get("full_zero_payload_closure_proven"))
        assert_true("unique qualifying HCI member", gates.get("hci_unique_qualifying_member"))
        assert_false("positive payload", gates.get("positive_payload_observed"))
        assert_equal("qualifying HCI member count", summary.get("qualifying_hci_member_count"), 1)
        assert_equal("qualifying HCI stream count", summary.get("qualifying_hci_stream_count"), 1)

        census = summary.get("selected_hci_census", {})
        assert_true("HCI coverage", census.get("coverage"))
        assert_true("HCI lifecycle complete", census.get("lifecycle_complete"))
        assert_true("HCI temporal correlation", census.get("temporal_correlation"))
        assert_true("HCI qualifies", census.get("qualifies"))
        assert_true("HCI zero payload proven", census.get("zero_payload_proven"))
        assert_false("HCI positive payload", census.get("positive_payload_observed"))
        for key in ("drops", "truncated_record_count", "payload_frame_count", "tx_payload_bytes", "rx_payload_bytes"):
            assert_equal(f"HCI {key}", census.get(key), 0)
        assert_equal("HCI SABM count", census.get("sabm_count"), 1)
        assert_equal("HCI DISC count", census.get("disc_count"), 1)
        assert_equal("target DLCI", census.get("target_dlci"), 6)

        tuple_ = summary.get("tuple", {})
        assert_equal("SCN", tuple_.get("scn"), 3)
        assert_equal("DLCI", tuple_.get("dlci"), 6)
        assert_equal("MTU", tuple_.get("mtu"), 990)
        assert_equal("native service class", tuple_.get("native_service_class_uuid"), "0x1101")

        orch = summary.get("strict_handoff_orchestration", {})
        for key in (
            "strict_runner_invoked",
            "fresh_disabled_baseline_attested",
            "private_handoff_ready_before_interval",
            "rfcomm_button_enabled_before_interval",
            "interval_started_after_readiness",
            "bugreport_collected_after_close",
            "probe_force_stopped_after_bugreport",
            "post_attempt_handoff_revoked_or_invalid",
        ):
            assert_true(f"orchestration {key}", orch.get(key))
        assert_equal("single connect request", orch.get("single_connect_request_count"), 1)
        assert_equal("strict runner exit code", orch.get("strict_runner_exit_code"), 0)

        source_private = str(private.get("strict_source_private_zip_sha256") or private.get("metadata", {}).get("strict_source_private_zip_sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", source_private):
            raise PublicationError("private analysis lacks a valid strict source archive SHA-256")
        handoff_hash = extract_handoff_hash(evidence_zf)
        hci_path, hci_hash = verify_hci_member(evidence_zf, summary)

        return ValidatedInputs(
            sanitized_sha256=hashes["sanitized"],
            analysis_sha256=hashes["analysis"],
            evidence_sha256=hashes["evidence"],
            source_private_sha256=source_private,
            source_handoff_sha256=handoff_hash,
            hci_member_sha256=hci_hash,
            hci_member_path=hci_path,
            frame_fingerprint_sha256=str(census.get("frame_fingerprint_sha256")),
            strict_runner_sha256=str(orch.get("strict_runner_sha256")),
            summary=summary,
            private=private,
            manifest_counts={
                "sanitized": san_count,
                "analysis": ana_count,
                "evidence": ev_count,
            },
        )
    finally:
        sanitized_zf.close()
        analysis_zf.close()
        evidence_zf.close()


def render_final_markdown(v: ValidatedInputs) -> str:
    s = v.summary
    c = s["selected_hci_census"]
    interval = s["metadata_interval"]
    return f"""# Final RFCOMM client zero-payload closure

**Release:** `{RELEASE}`  
**Authoritative runtime evidence:** `r1.3.3.2.25.2.3.2`  
**Acceptance:** `{EXPECTED_ACCEPTANCE}`

## Final conclusion

A single Android client-side RFCOMM attempt was provisioned through the strict private-handoff runner, attested ready before measurement, opened and closed exactly once, and correlated to one lossless HCI RFCOMM lifecycle. The target DLCI carried **zero application payload bytes in both directions**.

- Client-side lifecycle: **PROVEN**
- Same-attempt runtime tuple: **PROVEN**
- Matching RFCOMM open and close: **PROVEN**
- HCI SABM/UA and DISC/UA lifecycle: **PROVEN**
- TX application payload: **0 frames / 0 bytes**
- RX application payload: **0 frames / 0 bytes**
- Positive payload observed: **NO**
- Full zero-payload runtime closure: **PROVEN**

## Protocol invariants

| Field | Accepted value |
|---|---:|
| RFCOMM SCN | 3 |
| RFCOMM DLCI | 6 |
| RFCOMM MTU | 990 |
| Native service class | `0x1101` |

Dynamic process, slot, and port-handle values were correlated within the attempt but are intentionally omitted from the final public document.

## HCI proof boundary

| Gate | Result |
|---|---:|
| Measured interval | `{interval['start_utc']}` through `{interval['end_utc']}` |
| Unique qualifying HCI stream | YES |
| HCI records | {c['record_count']} |
| Records in proof window | {c['window_record_count']} |
| Dropped records | {c['drops']} |
| Truncated records | {c['truncated_record_count']} |
| Target DLCI frames | {c['target_frame_count']} |
| SABM / UA(open) | 1 / 1 |
| DISC / UA(close) | 1 / 1 |
| TX payload frames / bytes | {c['tx_payload_frame_count']} / {c['tx_payload_bytes']} |
| RX payload frames / bytes | {c['rx_payload_frame_count']} / {c['rx_payload_bytes']} |

Only non-control UIH information bytes on DLCI 6 count as application payload. Logcat silence, callback absence, and configuration values are not used as zero-payload proof.

## Strict private-handoff orchestration

The accepted run demonstrated all of the following:

- disabled-button baseline before provisioning;
- reuse of the accepted `r25.2.2.2` strict runner;
- fresh private-handoff readiness before the measured interval;
- exactly one enabled RFCOMM action and one connect request;
- bugreport collection only after explicit transport close;
- probe force-stop and private-handoff revocation after capture.

## Supersession

This result supersedes the earlier **bounded zero-payload conclusions** for the same research question. It does not invalidate their historical observations:

- `r1.3.3.2.25.2.2.2` remains evidence that the socket opened and application read/write counts were zero, but its same-attempt runtime-parameter closure was unresolved.
- `r1.3.3.2.25.2.2.2.1.3` remains the terminal archive-wide conclusion for the older archive: lifecycle proven, explicit zero-payload proof absent from that archive.
- `r1.3.3.2.25.2.3` and `.3.1` remain implementation history for the HCI capture and Pixel preflight repairs.
- `r1.3.3.2.25.2.3.2` supplies the authoritative new instrumented evidence that closes the remaining proof gap.

The supersession is **evidentiary**, not a rewrite of historical artifacts.

## Publication boundary

Private evidence and private-analysis archives must not be committed. Repository publication is limited to this final document, the public status summary, methodology, limitations, supersession map, and cryptographic evidence identities.
"""


def public_summary(v: ValidatedInputs) -> dict[str, Any]:
    s = v.summary
    c = s["selected_hci_census"]
    return {
        "schema": "rokid.r25.2.4.final-publication.v1",
        "release": RELEASE,
        "authoritative_evidence_release": "r1.3.3.2.25.2.3.2",
        "acceptance": EXPECTED_ACCEPTANCE,
        "qualification_outcome": EXPECTED_OUTCOME,
        "offline_publication_integration": True,
        "gates": {
            "android_client_lifecycle_proven": True,
            "same_attempt_runtime_tuple_proven": True,
            "matching_open_close_proven": True,
            "hci_dlci_lifecycle_proven": True,
            "hci_lossless_window": True,
            "tx_payload_bytes": 0,
            "rx_payload_bytes": 0,
            "positive_payload_observed": False,
            "full_zero_payload_closure_proven": True,
            "prior_bounded_result_superseded": True,
        },
        "protocol": {
            "scn": 3,
            "dlci": 6,
            "mtu": 990,
            "native_service_class_uuid": "0x1101",
        },
        "metadata_interval": s["metadata_interval"],
        "hci": {
            "datalink": c["datalink"],
            "record_count": c["record_count"],
            "window_record_count": c["window_record_count"],
            "drops": c["drops"],
            "truncated_record_count": c["truncated_record_count"],
            "target_frame_count": c["target_frame_count"],
            "sabm_count": c["sabm_count"],
            "disc_count": c["disc_count"],
            "tx_payload_frame_count": c["tx_payload_frame_count"],
            "tx_payload_bytes": c["tx_payload_bytes"],
            "rx_payload_frame_count": c["rx_payload_frame_count"],
            "rx_payload_bytes": c["rx_payload_bytes"],
            "frame_fingerprint_sha256": v.frame_fingerprint_sha256,
            "member_sha256": v.hci_member_sha256,
        },
        "strict_handoff": {
            "fresh_disabled_baseline_attested": True,
            "ready_before_interval": True,
            "single_connect_request": True,
            "bugreport_after_close": True,
            "post_attempt_revocation": True,
            "strict_runner_sha256": v.strict_runner_sha256,
        },
        "evidence_hashes_file": "r1.3.3.2.25.2.4-evidence-hashes.txt",
        "supersession_map_file": "r1.3.3.2.25.2.4-supersession-map.json",
    }


def supersession_map() -> dict[str, Any]:
    return {
        "schema": "rokid.connection-protocol.supersession.v1",
        "release": RELEASE,
        "authoritative_result": "r1.3.3.2.25.2.3.2",
        "final_publication": RELEASE,
        "entries": [
            {
                "release": "r1.3.3.2.25.2.2.2",
                "prior_outcome": "PASS_SOCKET_OPEN_ZERO_PAYLOAD_RUNTIME_PARAMETERS_UNRESOLVED",
                "status": "SUPERSEDED_FOR_FINAL_ZERO_PAYLOAD_QUALIFICATION",
                "preserved_scope": "historical socket-open and application-counter observation",
            },
            {
                "release": "r1.3.3.2.25.2.2.2.1.3",
                "prior_outcome": "PASS_BOUNDED_RFCOMM_CLIENT_LIFECYCLE_CLOSURE_ONLY",
                "status": "SUPERSEDED_FOR_FINAL_ZERO_PAYLOAD_QUALIFICATION",
                "preserved_scope": "terminal archive-only census for the older evidence archive",
            },
            {
                "release": "r1.3.3.2.25.2.3",
                "status": "IMPLEMENTATION_HISTORY",
                "preserved_scope": "initial HCI capture and frame-census design",
            },
            {
                "release": "r1.3.3.2.25.2.3.1",
                "status": "IMPLEMENTATION_HISTORY",
                "preserved_scope": "Pixel/AOSP HCI readiness correction",
            },
            {
                "release": "r1.3.3.2.25.2.3.2",
                "status": "AUTHORITATIVE_RUNTIME_EVIDENCE",
                "preserved_scope": "strict-handoff, same-attempt lifecycle, and lossless HCI zero-payload proof",
            },
        ],
    }


def evidence_hashes(v: ValidatedInputs) -> str:
    return "\n".join(
        [
            f"{v.sanitized_sha256}  r25.2.3.2-strict-handoff-hci-20260727T140508-sanitized-publication.zip",
            f"{v.analysis_sha256}  r25.2.3.2-strict-handoff-hci-20260727T140508-private-analysis.zip [PRIVATE; HASH ONLY]",
            f"{v.evidence_sha256}  r25.2.3.2-strict-handoff-hci-20260727T140508-private-evidence.zip [PRIVATE; HASH ONLY]",
            f"{v.source_private_sha256}  r25.2.2.1-cached-runtime-20260727T083553-private-evidence.zip [PRIVATE SOURCE; HASH ONLY]",
            f"{v.source_handoff_sha256}  accepted-r25.2.2.2-private-handoff [PRIVATE; HASH ONLY]",
            f"{v.hci_member_sha256}  bugreport.zip!/FS/data/misc/bluetooth/logs/btsnoop_hci.log [PRIVATE MEMBER; HASH ONLY]",
            f"{v.frame_fingerprint_sha256}  target-dlci-frame-fingerprint",
            f"{v.strict_runner_sha256}  installed-run_r1_3_3_2_25_2_2_2.sh",
            "",
        ]
    )


def methodology_text() -> str:
    return """# Methodology

The final publication is generated offline from the exact accepted `.3.2` sanitized publication, private analysis, and private evidence archives. The publisher verifies each outer ZIP hash, every internal SHA-256 manifest, agreement between private and sanitized status summaries, and the SHA-256 of the selected btsnoop member nested inside the private bugreport.

The runtime proof combines one Android client-side RFCOMM lifecycle with one temporally correlated, lossless HCI RFCOMM lifecycle. Application payload is defined only as non-control UIH information bytes on target DLCI 6 between the SABM/UA open boundary and DISC/UA close boundary.

The repository integration does not contact a phone or glasses, does not copy private archive bytes, and does not create a Git commit or push.
"""


def limitations_text() -> str:
    return """# Limitations

The accepted result is scoped to the observed Android client-side RFCOMM connection-only attempt and the protocol values SCN 3, DLCI 6, and MTU 990. It does not identify or authorize an application-layer protocol, does not establish that later sessions will remain payload-free, and does not imply support for independent GATT or other channels.

Cryptographic hashes permit identity and integrity checks but do not make private evidence suitable for publication. The private evidence and private-analysis ZIPs remain excluded from Git.
"""


def readme_block() -> str:
    return f"""{README_BEGIN}
## Current RFCOMM connection-only conclusion

The authoritative result is **full Android client RFCOMM zero-payload runtime closure**, proven by the strict private-handoff `.3.2` run and a lossless HCI DLCI-frame census.

- Final publication: [`r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md`](r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md)
- Runtime status: [`r1.3.3.2.25.2.4-runtime-status-summary.json`](r1.3.3.2.25.2.4-runtime-status-summary.json)
- Evidence identities: [`r1.3.3.2.25.2.4-evidence-hashes.txt`](r1.3.3.2.25.2.4-evidence-hashes.txt)
- Supersession map: [`r1.3.3.2.25.2.4-supersession-map.json`](r1.3.3.2.25.2.4-supersession-map.json)

Accepted invariants: SCN `3`, DLCI `6`, MTU `990`; TX payload `0` bytes; RX payload `0` bytes. Earlier bounded results remain historical evidence but are superseded for the final zero-payload qualification.
{README_END}"""


def update_readme(path: Path) -> tuple[str | None, str]:
    original = path.read_text(encoding="utf-8") if path.exists() else None
    base = original if original is not None else "# Connection Protocol Research\n"
    block = readme_block()
    pattern = re.compile(re.escape(README_BEGIN) + r".*?" + re.escape(README_END), re.DOTALL)
    if pattern.search(base):
        updated = pattern.sub(block, base)
    else:
        updated = base.rstrip() + "\n\n" + block + "\n"
    return original, updated


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def privacy_scan_generated(paths: Iterable[Path]) -> None:
    patterns = {
        "raw serial assignment": re.compile(
            r"""(?i)["']?(?:[a-z0-9]+[ _-]*)?serial(?:_number)?["']?\s*[:=]\s*["']?[a-z0-9._:-]{6,}"""
        ),
        "absolute macOS path": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
        "full Bluetooth address": re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])"),
        "raw endpoint suffix": re.compile(r"(?i)xx:xx:xx:xx:[0-9a-f]{2}:[0-9a-f]{2}"),
        "phone serial hash field": re.compile(r"phone_serial_sha256"),
    }
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for label, pattern in patterns.items():
            if pattern.search(text):
                raise PublicationError(f"generated publication contains {label}: {path}")


def create_publication_zip(source_dir: Path, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                arc = path.relative_to(source_dir.parent).as_posix()
                info = zipfile.ZipInfo(arc)
                info.date_time = (2026, 7, 27, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                zf.writestr(info, path.read_bytes())


def run(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.repo.resolve()
    if not repo.is_dir():
        raise PublicationError(f"repository not found: {repo}")
    docs = repo / "docs/research/connection-protocol"
    output = args.output.resolve()
    if output.exists():
        raise PublicationError(f"output already exists: {output}")

    v = validate_inputs(
        args.sanitized_publication_zip.resolve(),
        args.private_analysis_zip.resolve(),
        args.private_evidence_zip.resolve(),
        args.expected_sanitized_sha256,
        args.expected_analysis_sha256,
        args.expected_evidence_sha256,
    )

    output.mkdir(parents=True)

    names = {
        "final": "r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md",
        "summary": "r1.3.3.2.25.2.4-runtime-status-summary.json",
        "hashes": "r1.3.3.2.25.2.4-evidence-hashes.txt",
        "methodology": "r1.3.3.2.25.2.4-methodology.md",
        "limitations": "r1.3.3.2.25.2.4-limitations.md",
        "supersession": "r1.3.3.2.25.2.4-supersession-map.json",
    }
    generated = output / "publication"
    generated.mkdir()
    atomic_write(generated / names["final"], render_final_markdown(v).encode())
    write_json(generated / names["summary"], public_summary(v))
    atomic_write(generated / names["hashes"], evidence_hashes(v).encode())
    atomic_write(generated / names["methodology"], methodology_text().encode())
    atomic_write(generated / names["limitations"], limitations_text().encode())
    write_json(generated / names["supersession"], supersession_map())

    publication_files = [generated / n for n in names.values()]
    privacy_scan_generated(publication_files)

    pub_manifest_lines = []
    for path in sorted(publication_files):
        pub_manifest_lines.append(f"{sha256_file(path)}  {path.name}")
    manifest_path = generated / "SHA256SUMS.txt"
    atomic_write(manifest_path, ("\n".join(pub_manifest_lines) + "\n").encode())

    # Build an integration plan and backups before touching the repository.
    readme_path = docs / "README.md"
    original_readme, updated_readme = update_readme(readme_path)
    backup_dir = output / "repository-backup"
    if original_readme is not None:
        backup_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(backup_dir / "README.md.before-r25.2.4", original_readme.encode())

    destinations = {key: docs / name for key, name in names.items()}
    for key, dest in destinations.items():
        src = generated / names[key]
        if dest.exists() and dest.read_bytes() != src.read_bytes():
            raise PublicationError(f"refusing to overwrite different existing publication file: {dest}")

    # Install publication files and managed README block.
    docs.mkdir(parents=True, exist_ok=True)
    for key, dest in destinations.items():
        atomic_write(dest, (generated / names[key]).read_bytes())
    atomic_write(readme_path, updated_readme.encode())

    installed_paths = [*destinations.values(), readme_path]
    privacy_scan_generated([*destinations.values()])

    publication_zip = output.with_name(output.name + "-sanitized-publication.zip")
    create_publication_zip(generated, publication_zip)
    publication_zip_sha = sha256_file(publication_zip)

    report = {
        "schema": "rokid.r25.2.4.integration-report.v1",
        "release": RELEASE,
        "acceptance": "PASS_FINAL_RFCOMM_ZERO_PAYLOAD_PUBLICATION_INTEGRATION",
        "inputs": {
            "sanitized_publication_zip_sha256": v.sanitized_sha256,
            "private_analysis_zip_sha256": v.analysis_sha256,
            "private_evidence_zip_sha256": v.evidence_sha256,
            "source_private_zip_sha256": v.source_private_sha256,
            "source_handoff_sha256": v.source_handoff_sha256,
            "hci_member_sha256": v.hci_member_sha256,
            "hci_member_path": v.hci_member_path,
            "manifest_entry_counts": v.manifest_counts,
        },
        "repository": {
            "root": str(repo),
            "installed_files": [str(p.relative_to(repo)) for p in installed_paths],
            "readme_managed_block": True,
            "private_archives_copied": False,
            "git_commit_created": False,
            "git_push_performed": False,
        },
        "output": {
            "directory": str(output),
            "sanitized_publication_zip": str(publication_zip),
            "sanitized_publication_zip_sha256": publication_zip_sha,
        },
    }
    write_json(output / "integration-report.json", report)

    output_hashes = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            output_hashes.append(f"{sha256_file(path)}  {path.relative_to(output).as_posix()}")
    atomic_write(output / "SHA256SUMS.txt", ("\n".join(output_hashes) + "\n").encode())

    return report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--sanitized-publication-zip", type=Path, required=True)
    p.add_argument("--private-analysis-zip", type=Path, required=True)
    p.add_argument("--private-evidence-zip", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--expected-sanitized-sha256", required=True)
    p.add_argument("--expected-analysis-sha256", required=True)
    p.add_argument("--expected-evidence-sha256", required=True)
    return p


def main() -> int:
    try:
        report = run(build_parser().parse_args())
    except (PublicationError, zipfile.BadZipFile, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"R25_2_4_ERROR={exc}", file=sys.stderr)
        print("R1_3_3_2_25_2_4_ACCEPTANCE=FAIL", file=sys.stderr)
        return 1

    inputs = report["inputs"]
    output = report["output"]
    print("R25_2_4_OUTER_ARCHIVE_HASH_GATE=PASS")
    print("R25_2_4_INTERNAL_MANIFEST_GATE=PASS")
    print("R25_2_4_PRIVATE_SANITIZED_AGREEMENT_GATE=PASS")
    print("R25_2_4_HCI_MEMBER_HASH_GATE=PASS")
    print("R25_2_4_FULL_ZERO_PAYLOAD_CLOSURE_GATE=PASS")
    print("R25_2_4_PRIOR_BOUNDED_RESULT_SUPERSESSION=PASS")
    print("R25_2_4_PUBLICATION_PRIVACY_GATE=PASS")
    print("R25_2_4_REPOSITORY_DOCUMENTATION_INTEGRATION=PASS")
    print("R25_2_4_PRIVATE_ARCHIVES_COPIED=NO")
    print(f"R25_2_4_SANITIZED_SOURCE_ZIP_SHA256={inputs['sanitized_publication_zip_sha256']}")
    print(f"R25_2_4_PRIVATE_ANALYSIS_ZIP_SHA256={inputs['private_analysis_zip_sha256']}")
    print(f"R25_2_4_PRIVATE_EVIDENCE_ZIP_SHA256={inputs['private_evidence_zip_sha256']}")
    print(f"R25_2_4_FINAL_PUBLICATION_ZIP={output['sanitized_publication_zip']}")
    print(f"R25_2_4_FINAL_PUBLICATION_ZIP_SHA256={output['sanitized_publication_zip_sha256']}")
    print("R25_2_4_QUALIFICATION_OUTCOME=RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS")
    print("R1_3_3_2_25_2_4_ACCEPTANCE=PASS_FINAL_RFCOMM_ZERO_PAYLOAD_PUBLICATION_INTEGRATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
