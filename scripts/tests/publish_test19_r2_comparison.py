#!/usr/bin/env python3
"""Verify two private Test 19 r2 ZIPs and emit sanitized comparison outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

EXPECTED_SCHEMA = "rokid.test19-r2.cxrl-event.v1"
EXPECTED_SUMMARY_SCHEMA = "rokid.test19-r2.cxrl-summary.v1"
EXPECTED_CLASSIFICATION = "CXR_L_CONNECTION_AND_STOCK_RECOVERY_PASS"
EXPECTED_HI_ROKID = "G1.11.11.0727"
EXPECTED_PACKAGE = "org.aimindseye.rokid.cxrlqualification"
EXPECTED_SEQUENCE = [
    "run_started",
    "hi_rokid_environment",
    "authorization_requested",
    "authorization_activity_started",
    "authorization_result",
    "connection_attempt_started",
    "session_config_result",
    "sdk_connect_invoked",
    "manual_service_bind_result",
    "callback_cxrl_connected",
    "callback_glass_bt_connected",
    "qualification_terminal",
    "disconnect_invoked",
    "disconnect_result",
    "run_completed",
]


@dataclass(frozen=True)
class RunEvidence:
    label: str
    zip_sha256: str
    internal_manifest_verified: bool
    summary: dict[str, Any]
    events: list[dict[str, Any]]
    host_recovery: dict[str, Any]
    metadata: dict[str, str]
    screenshot_sha256: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_manifest(text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ValueError(f"malformed SHA-256 manifest line: {line!r}")
        rows.append((match.group(1), match.group(2)))
    if not rows:
        raise ValueError("empty SHA-256 manifest")
    return rows


def single_member(names: list[str], basename: str) -> str:
    matches = [name for name in names if PurePosixPath(name).name == basename]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {basename}, found {len(matches)}")
    return matches[0]


def parse_metadata(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def load_run(path: Path, label: str, expected_firmware: str) -> RunEvidence:
    raw_zip = path.read_bytes()
    zip_hash = sha256_bytes(raw_zip)
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        manifest_name = single_member(names, "SHA256SUMS-private.txt")
        manifest_rows = parse_manifest(archive.read(manifest_name).decode("utf-8"))
        verified = True
        manifest_parent = PurePosixPath(manifest_name).parent
        for expected, member in manifest_rows:
            relative = member[2:] if member.startswith("./") else member
            archive_member = str(manifest_parent / relative)
            if archive_member not in names:
                raise ValueError(f"manifest member missing from ZIP: {member}")
            actual = sha256_bytes(archive.read(archive_member))
            if actual != expected:
                verified = False
                raise ValueError(f"manifest hash mismatch: {member}")

        summary = json.loads(archive.read(single_member(names, "summary.json")))
        host_recovery = json.loads(archive.read(single_member(names, "host-recovery.json")))
        metadata = parse_metadata(
            archive.read(single_member(names, "run-metadata.txt")).decode("utf-8")
        )
        screenshot_line = archive.read(
            single_member(names, "firmware-screenshot.sha256.txt")
        ).decode("utf-8").strip()
        screenshot_hash = screenshot_line.split()[0]
        event_lines = archive.read(single_member(names, "app-events.jsonl")).decode("utf-8").splitlines()
        events = [json.loads(line) for line in event_lines if line.strip()]

    if summary.get("schema") != EXPECTED_SUMMARY_SCHEMA:
        raise ValueError(f"{label}: unexpected summary schema")
    if summary.get("classification") != EXPECTED_CLASSIFICATION:
        raise ValueError(f"{label}: qualification did not pass")
    if summary.get("exit_code") != 0 or summary.get("qualification_pass") is not True:
        raise ValueError(f"{label}: summary exit/pass mismatch")
    if host_recovery.get("hi_rokid_recovery_confirmed") is not True:
        raise ValueError(f"{label}: Hi Rokid recovery was not confirmed")
    if metadata.get("FIRMWARE") != expected_firmware:
        raise ValueError(f"{label}: firmware mismatch")
    if metadata.get("HI_ROKID_VERSION") != EXPECTED_HI_ROKID:
        raise ValueError(f"{label}: Hi Rokid version mismatch")
    if metadata.get("APP_PACKAGE") != EXPECTED_PACKAGE:
        raise ValueError(f"{label}: app package mismatch")
    if any(event.get("schema") != EXPECTED_SCHEMA for event in events):
        raise ValueError(f"{label}: unexpected event schema")
    if [event.get("event_type") for event in events] != EXPECTED_SEQUENCE:
        raise ValueError(f"{label}: event sequence mismatch")

    return RunEvidence(
        label=label,
        zip_sha256=zip_hash,
        internal_manifest_verified=verified,
        summary=summary,
        events=events,
        host_recovery=host_recovery,
        metadata=metadata,
        screenshot_sha256=screenshot_hash,
    )


def event_details(run: RunEvidence, event_type: str) -> dict[str, Any]:
    matches = [event for event in run.events if event.get("event_type") == event_type]
    if len(matches) != 1:
        raise ValueError(f"{run.label}: expected one {event_type}")
    value = matches[0].get("details", {})
    if not isinstance(value, dict):
        raise ValueError(f"{run.label}: malformed details for {event_type}")
    return value


def behavioral_signature(run: RunEvidence) -> list[dict[str, Any]]:
    signature: list[dict[str, Any]] = []
    for event in run.events:
        details = dict(event.get("details", {}))
        if event.get("event_type") == "run_started":
            details.pop("evidence_path", None)
        signature.append({"event_type": event.get("event_type"), "details": details})
    return signature


def public_run(run: RunEvidence) -> dict[str, Any]:
    start = event_details(run, "run_started")
    environment = event_details(run, "hi_rokid_environment")
    sdk_connect = event_details(run, "sdk_connect_invoked")
    fallback = event_details(run, "manual_service_bind_result")
    terminal = event_details(run, "qualification_terminal")
    disconnect = event_details(run, "disconnect_result")
    return {
        "firmware": run.metadata["FIRMWARE"],
        "classification": run.summary["classification"],
        "qualification_pass": run.summary["qualification_pass"],
        "event_count": run.summary["event_count"],
        "hi_rokid_version": environment.get("version_name"),
        "authorization_token_value_logged": False,
        "runtime_event_app_version": start.get("app_version"),
        "sdk_connect_return_value": sdk_connect.get("return_value"),
        "fallback_service_bind_reason": fallback.get("reason"),
        "fallback_service_bind_started": fallback.get("bind_started"),
        "cxrl_callback_connected": event_details(run, "callback_cxrl_connected").get("connected"),
        "glass_bt_callback_connected": event_details(run, "callback_glass_bt_connected").get("connected"),
        "terminal_outcome": terminal.get("outcome"),
        "sdk_disconnect_returned": disconnect.get("sdk_disconnect_returned"),
        "legacy_manual_unbind_error_class": disconnect.get("manual_unbind_error_class"),
        "hi_rokid_recovery_confirmed": run.host_recovery.get("hi_rokid_recovery_confirmed"),
        "private_evidence_zip_sha256": run.zip_sha256,
        "firmware_screenshot_sha256": run.screenshot_sha256,
        "internal_hash_manifest_verified": run.internal_manifest_verified,
    }


def build_publication(
    run_a: RunEvidence,
    run_b: RunEvidence,
    governed_version: str,
    governed_version_code: int,
    governed_apk_sha256: str,
) -> dict[str, Any]:
    sequence_equal = [e["event_type"] for e in behavioral_signature(run_a)] == [
        e["event_type"] for e in behavioral_signature(run_b)
    ]
    behavior_equal = behavioral_signature(run_a) == behavioral_signature(run_b)
    return {
        "schema": "rokid.test19-r2.cxrl-firmware-comparison.v1",
        "publication": "Test 19 r2.4",
        "status": "FINAL_COMPARISON_PUBLISHED",
        "qualification_app": {
            "package": EXPECTED_PACKAGE,
            "governed_install_version_name": governed_version,
            "governed_install_version_code": governed_version_code,
            "governed_install_apk_sha256": governed_apk_sha256,
            "runtime_event_label_consistent": False,
            "runtime_event_label_observed": event_details(run_a, "run_started").get("app_version"),
            "runtime_event_label_repair": "dynamic_package_manager_identity_in_r2.4",
        },
        "stack": {
            "hi_rokid_package": "com.rokid.sprite.global.aiapp",
            "hi_rokid_version": EXPECTED_HI_ROKID,
            "cxr_l_coordinate": "com.rokid.cxr:client-l:1.0.1",
        },
        "runs": [public_run(run_a), public_run(run_b)],
        "comparison": {
            "event_type_sequence_equal": sequence_equal,
            "behavioral_signature_equal_after_run_specific_normalization": behavior_equal,
            "firmware_regression_observed": False,
            "connection_path": "FALLBACK_SERVICE_BIND_ASSISTED",
            "bounded_conclusion": (
                "No CXR-L compatibility regression was observed between the tested "
                "1.22 and 1.23 firmware builds."
            ),
        },
        "runtime_repairs": {
            "evidence_label": {
                "problem": "hardcoded stale app_version field",
                "repair": "derive versionName and versionCode from PackageManager at runtime",
            },
            "disconnect_cleanup": {
                "problem": "redundant manual unbind after successful SDK disconnect",
                "repair": (
                    "skip manual unbind when SDK disconnect succeeds; attempt manual unbind only "
                    "when a fallback bind started and SDK disconnect did not complete"
                ),
                "duplicate_disconnect_guard": True,
            },
            "retroactive_effect_on_accepted_runs": False,
        },
        "privacy": {
            "authorization_token_value_published": False,
            "phone_serial_published": False,
            "raw_bluetooth_address_published": False,
            "media_payload_published": False,
            "private_zip_bytes_committed": False,
        },
        "limitations": [
            "One controlled connection run was performed per firmware version.",
            "The successful path required fallback binding after CXRLink.connect() returned false.",
            "The comparison does not qualify media, AI, APK upload, reboot recovery, or Hi Rokid replacement.",
            "The r2.4 runtime repairs are forward-looking and do not rewrite the accepted private evidence.",
        ],
    }


def markdown(value: dict[str, Any]) -> str:
    a, b = value["runs"]
    return f"""# Test 19 r2.4 — Final CXR-L Firmware Comparison

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-07-31 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Validated |
| Last reviewed | 2026-07-31 |

## Final result

No CXR-L compatibility regression was observed between firmware
`{a['firmware']}` and `{b['firmware']}` for the tested stack. Both controlled
runs authorized through Hi Rokid, configured a `CUSTOMAPP` session, received
`onCXRLConnected(true)` and `onGlassBtConnected(true)`, disconnected through
the SDK, and returned to a working stock Hi Rokid session.

| Check | Firmware 1.22 | Firmware 1.23 |
|---|---|---|
| Qualification | `{a['classification']}` | `{b['classification']}` |
| Event count | `{a['event_count']}` | `{b['event_count']}` |
| SDK `connect()` return | `{str(a['sdk_connect_return_value']).lower()}` | `{str(b['sdk_connect_return_value']).lower()}` |
| Fallback service bind | `{str(a['fallback_service_bind_started']).lower()}` | `{str(b['fallback_service_bind_started']).lower()}` |
| CXR-L callback | `{str(a['cxrl_callback_connected']).lower()}` | `{str(b['cxrl_callback_connected']).lower()}` |
| Glasses Bluetooth callback | `{str(a['glass_bt_callback_connected']).lower()}` | `{str(b['glass_bt_callback_connected']).lower()}` |
| SDK disconnect | `{str(a['sdk_disconnect_returned']).lower()}` | `{str(b['sdk_disconnect_returned']).lower()}` |
| Hi Rokid recovery | `{str(a['hi_rokid_recovery_confirmed']).lower()}` | `{str(b['hi_rokid_recovery_confirmed']).lower()}` |

## Connection-path finding

In both runs, `CXRLink.connect()` returned `false`. The client then bound the
exported CXR-L media service using the SDK-owned `ServiceConnection`. Both
required callbacks arrived and the qualification completed. The accepted
classification is therefore **fallback-service-bind assisted**, not a claim
that the direct SDK call alone completed the connection.

## Runtime repairs in r2.4

The accepted r2.3.2 event files contain a stale hardcoded runtime label
`{value['qualification_app']['runtime_event_label_observed']}` even though the
governed APK identity was `{value['qualification_app']['governed_install_version_name']}`.
r2.4 reads version name and version code from Android `PackageManager` at
runtime instead of embedding a string in the event logger.

Both accepted runs also show `java.lang.IllegalArgumentException` when the app
attempted a redundant manual unbind after `CXRLink.disconnect()` succeeded.
r2.4 treats successful SDK disconnect as cleanup ownership, skips that manual
unbind, attempts manual unbind only after SDK disconnect failure, and suppresses
duplicate disconnect calls.

These repairs do not rewrite or reinterpret the accepted private evidence.

## Evidence identities

- Firmware 1.22 private ZIP SHA-256: `{a['private_evidence_zip_sha256']}`
- Firmware 1.22 screenshot SHA-256: `{a['firmware_screenshot_sha256']}`
- Firmware 1.23 private ZIP SHA-256: `{b['private_evidence_zip_sha256']}`
- Firmware 1.23 screenshot SHA-256: `{b['firmware_screenshot_sha256']}`
- Governed r2.3.2 APK SHA-256: `{value['qualification_app']['governed_install_apk_sha256']}`

Private ZIP bytes, authorization-token values, phone serials, raw Bluetooth
addresses, and media payloads are not committed.

## Boundaries

- one connection run per firmware;
- exact Hi Rokid `{EXPECTED_HI_ROKID}` and CXR-L `client-l:1.0.1`;
- no media, AI, upload, reboot-recovery, or independent-Hi-Rokid qualification;
- no performance conclusion from operator-driven timing.
"""


def hashes_text(value: dict[str, Any]) -> str:
    a, b = value["runs"]
    lines = [
        "# Test 19 r2.4 public evidence identities",
        f"run_a_private_zip_sha256={a['private_evidence_zip_sha256']}",
        f"run_a_firmware_screenshot_sha256={a['firmware_screenshot_sha256']}",
        f"run_b_private_zip_sha256={b['private_evidence_zip_sha256']}",
        f"run_b_firmware_screenshot_sha256={b['firmware_screenshot_sha256']}",
        f"governed_r2_3_2_apk_sha256={value['qualification_app']['governed_install_apk_sha256']}",
        "private_zip_bytes_committed=no",
        "authorization_token_value_published=no",
        "phone_serial_published=no",
        "raw_bluetooth_address_published=no",
        "media_payload_published=no",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-a-zip", required=True)
    parser.add_argument("--run-b-zip", required=True)
    parser.add_argument("--run-a-firmware", default="1.22.009-20260710-151201")
    parser.add_argument("--run-b-firmware", default="1.23.009-20260725-153201")
    parser.add_argument("--governed-app-version", default="2.3.2-test19-r2.3.2")
    parser.add_argument("--governed-app-version-code", type=int, default=6)
    parser.add_argument("--governed-apk-sha256", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-hashes", required=True)
    args = parser.parse_args()

    try:
        run_a = load_run(Path(args.run_a_zip), "run_a", args.run_a_firmware)
        run_b = load_run(Path(args.run_b_zip), "run_b", args.run_b_firmware)
        value = build_publication(
            run_a,
            run_b,
            args.governed_app_version,
            args.governed_app_version_code,
            args.governed_apk_sha256,
        )
        if value["comparison"]["event_type_sequence_equal"] is not True:
            raise ValueError("event-type sequences differ")
        if value["comparison"]["behavioral_signature_equal_after_run_specific_normalization"] is not True:
            raise ValueError("material behavior differs between runs")

        output_json = Path(args.output_json)
        output_md = Path(args.output_md)
        output_hashes = Path(args.output_hashes)
        for output in (output_json, output_md, output_hashes):
            output.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output_md.write_text(markdown(value), encoding="utf-8")
        output_hashes.write_text(hashes_text(value), encoding="utf-8")
    except Exception as error:  # noqa: BLE001
        print("TEST19_R2_4_COMPARISON_PUBLICATION=FAIL")
        print(f"ERROR_CLASS={error.__class__.__name__}")
        print(f"ERROR={error}")
        return 1

    print("TEST19_R2_4_RUN_A_PRIVATE_HASH_MANIFEST=PASS")
    print("TEST19_R2_4_RUN_B_PRIVATE_HASH_MANIFEST=PASS")
    print("TEST19_R2_4_EVENT_SEQUENCE_COMPARISON=PASS")
    print("TEST19_R2_4_BEHAVIORAL_SIGNATURE_COMPARISON=PASS")
    print("TEST19_R2_4_PRIVATE_BYTES_PUBLISHED=NO")
    print("TEST19_R2_4_COMPARISON_PUBLICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
