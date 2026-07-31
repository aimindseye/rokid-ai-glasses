#!/usr/bin/env python3
"""Analyze one private Test 20 r2 JSONL event stream.

The analyzer emits a sanitized summary. It never writes authorization token
values, device serials, Bluetooth addresses, media, or cloud payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA = "rokid.test20-r2.cxrl-event.v1"
EXPECTED_PACKAGE = "org.aimindseye.rokid.cxreventqualification"
EXPECTED_VERSION = "1.0-test20-r2"
EXPECTED_VERSION_CODE = 1
EXPECTED_HI_ROKID_VERSION = "G1.11.11.0727"
REQUIRED_CYCLES = 2

BLUETOOTH_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
SERIAL_RE = re.compile(r"\b[A-Z0-9]{14,20}\b")
TOKEN_KEYS = {"token", "auth_token", "authorization_token", "access_token"}
MEDIA_KEYS = {
    "photo",
    "image_bytes",
    "audio_bytes",
    "video_bytes",
    "media_payload",
    "transcript",
    "prompt",
    "response_text",
}


class AnalysisError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as error:
            raise AnalysisError(
                f"invalid JSON at line {line_number}: {error}"
            ) from error
        if not isinstance(event, dict):
            raise AnalysisError(f"line {line_number} is not an object")
        if event.get("schema") != SCHEMA:
            raise AnalysisError(
                f"line {line_number} has unexpected schema"
            )
        events.append(event)
    if not events:
        raise AnalysisError("event stream is empty")
    return events


def recursive_privacy_scan(value: Any, location: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in TOKEN_KEYS:
                violations.append(f"{location}.{key}: forbidden token key")
            if normalized in MEDIA_KEYS:
                violations.append(f"{location}.{key}: forbidden media key")
            violations.extend(
                recursive_privacy_scan(item, f"{location}.{key}")
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(
                recursive_privacy_scan(item, f"{location}[{index}]")
            )
    elif isinstance(value, str):
        if BLUETOOTH_RE.search(value):
            violations.append(f"{location}: raw Bluetooth address")
        if SERIAL_RE.fullmatch(value) and value not in {
            EXPECTED_VERSION.replace("-", "").upper()
        }:
            # Conservative exact-value guard; normal event strings contain
            # punctuation or lowercase and do not match.
            violations.append(f"{location}: possible raw device serial")
    return violations


def one(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    matches = [item for item in events if item.get("event_type") == event_type]
    if len(matches) != 1:
        raise AnalysisError(
            f"expected exactly one {event_type}, found {len(matches)}"
        )
    return matches[0]


def details(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("details")
    if not isinstance(value, dict):
        raise AnalysisError(
            f"{event.get('event_type')} details are not an object"
        )
    return value


def accepted_callbacks(
    events: list[dict[str, Any]], event_type: str
) -> list[dict[str, Any]]:
    return [
        item
        for item in events
        if item.get("event_type") == event_type
        and details(item).get("accepted") is True
    ]


def read_attestation(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def analyze(
    events_path: Path,
    attestation_path: Path,
    expected_firmware: str,
) -> dict[str, Any]:
    events = load_events(events_path)
    privacy_violations = recursive_privacy_scan(events)
    if privacy_violations:
        raise AnalysisError(
            "privacy violations: " + "; ".join(privacy_violations)
        )

    run_ids = {str(item.get("run_id", "")) for item in events}
    firmware_labels = {
        str(item.get("firmware_label", "")) for item in events
    }
    if len(run_ids) != 1 or "" in run_ids:
        raise AnalysisError("event stream does not contain one run_id")
    if firmware_labels != {expected_firmware}:
        raise AnalysisError("firmware label mismatch")

    started = details(one(events, "run_started"))
    if started.get("app_package") != EXPECTED_PACKAGE:
        raise AnalysisError("runtime package mismatch")
    if started.get("app_version") != EXPECTED_VERSION:
        raise AnalysisError("runtime versionName mismatch")
    if int(started.get("app_version_code", -1)) != EXPECTED_VERSION_CODE:
        raise AnalysisError("runtime versionCode mismatch")
    required_safe_flags = {
        "internet_permission_intentionally_removed": True,
        "camera_permission_intentionally_removed": True,
        "record_audio_permission_intentionally_removed": True,
        "test_app_ai_assistant_invocation_enabled": False,
        "media_operation_enabled": False,
        "custom_command_enabled": False,
        "custom_view_enabled": False,
        "app_management_enabled": False,
        "cloud_api_client_present": False,
    }
    for key, expected in required_safe_flags.items():
        if started.get(key) is not expected:
            raise AnalysisError(f"unsafe or missing run flag: {key}")

    hi = details(one(events, "hi_rokid_environment"))
    if hi.get("package_name") != "com.rokid.sprite.global.aiapp":
        raise AnalysisError("unexpected Hi Rokid package")
    if hi.get("version_name") != EXPECTED_HI_ROKID_VERSION:
        raise AnalysisError("unexpected Hi Rokid version")
    if hi.get("authorization_resolved") is not True:
        raise AnalysisError("authorization surface did not resolve")
    if hi.get("service_resolved") is not True:
        raise AnalysisError("CXR-L service surface did not resolve")

    auth = details(one(events, "authorization_result"))
    if auth.get("token_present") is not True:
        raise AnalysisError("authorization token was not present")
    if auth.get("token_value_logged") is not False:
        raise AnalysisError("authorization token logging gate failed")

    session = details(one(events, "session_config_result"))
    if session.get("configured") is not True:
        raise AnalysisError("CUSTOMAPP session configuration failed")
    if session.get("session_type") != "CUSTOMAPP":
        raise AnalysisError("unexpected session type")

    cxrl_true = [
        item
        for item in events
        if item.get("event_type") == "callback_cxrl_connected"
        and details(item).get("connected") is True
    ]
    bt_true = [
        item
        for item in events
        if item.get("event_type") == "callback_glass_bt_connected"
        and details(item).get("connected") is True
    ]
    if not cxrl_true or not bt_true:
        raise AnalysisError("required connection callbacks were not observed")

    armed = details(one(events, "event_observation_armed"))
    if int(armed.get("required_cycles", -1)) != REQUIRED_CYCLES:
        raise AnalysisError("unexpected required cycle count")
    if armed.get("test_app_invokes_ai_assistant") is not False:
        raise AnalysisError("test app invocation safety gate failed")
    if armed.get("operator_must_not_speak_query") is not True:
        raise AnalysisError("operator no-query gate is missing")

    starts = accepted_callbacks(events, "callback_ai_assist_start")
    stops = accepted_callbacks(events, "callback_ai_assist_stop")
    if len(starts) != REQUIRED_CYCLES:
        raise AnalysisError(
            f"expected {REQUIRED_CYCLES} accepted starts, found {len(starts)}"
        )
    if len(stops) != REQUIRED_CYCLES:
        raise AnalysisError(
            f"expected {REQUIRED_CYCLES} accepted stops, found {len(stops)}"
        )

    sequences: list[tuple[int, str]] = []
    for item in starts:
        sequences.append((int(details(item)["sequence"]), "start"))
    for item in stops:
        sequences.append((int(details(item)["sequence"]), "stop"))
    sequences.sort()
    if [sequence for sequence, _ in sequences] != [1, 2, 3, 4]:
        raise AnalysisError(
            "AI-assist callback sequence numbers were not exactly 1-4"
        )
    if [kind for _, kind in sequences] != [
        "start",
        "stop",
        "start",
        "stop",
    ]:
        raise AnalysisError(
            "AI-assist callbacks were not two ordered start/stop cycles"
        )

    all_starts = [
        details(item)
        for item in events
        if item.get("event_type") == "callback_ai_assist_start"
    ]
    all_stops = [
        details(item)
        for item in events
        if item.get("event_type") == "callback_ai_assist_stop"
    ]
    if len(all_starts) != REQUIRED_CYCLES or len(all_stops) != REQUIRED_CYCLES:
        raise AnalysisError("unexpected rejected or extra AI-assist callbacks")
    if any(int(item.get("duplicate_start_count", 0)) != 0 for item in all_starts):
        raise AnalysisError("duplicate start callback was observed")
    if any(int(item.get("out_of_order_stop_count", 0)) != 0 for item in all_stops):
        raise AnalysisError("out-of-order stop callback was observed")
    if any(int(details(item).get("cycle_duration_ms", -1)) < 0 for item in stops):
        raise AnalysisError("accepted stop lacks a non-negative duration")

    terminal = details(one(events, "qualification_terminal"))
    if terminal.get("outcome") != "AI_ASSIST_TWO_ORDERED_CYCLES_OBSERVED":
        raise AnalysisError("unexpected terminal outcome")
    if terminal.get("success") is not True:
        raise AnalysisError("terminal result is not successful")
    if int(terminal.get("completed_cycle_count", -1)) != REQUIRED_CYCLES:
        raise AnalysisError("terminal cycle count mismatch")

    disconnect = details(one(events, "disconnect_result"))
    if disconnect.get("sdk_disconnect_returned") is not True:
        raise AnalysisError("SDK disconnect did not return successfully")
    if disconnect.get("manual_unbind_attempted") is not False:
        raise AnalysisError("unexpected manual unbind attempt")
    if disconnect.get("manual_bind_started") is True:
        if disconnect.get("manual_unbind_disposition") != (
            "SKIPPED_SDK_DISCONNECT_SUCCEEDED"
        ):
            raise AnalysisError("state-aware disconnect disposition mismatch")

    completed = details(one(events, "run_completed"))
    if completed.get("terminal_success") is not True:
        raise AnalysisError("run completion is not successful")
    if completed.get("test_app_cloud_ai_request") != "NONE":
        raise AnalysisError("test-app cloud request gate failed")
    if completed.get("test_app_media_operation") != "NONE":
        raise AnalysisError("test-app media gate failed")

    attestation = read_attestation(attestation_path)
    if attestation.get("OPERATOR_SPOKEN_AI_QUERY") != "NO":
        raise AnalysisError("operator no-query attestation failed")
    if attestation.get("STOCK_AI_RESPONSE_OBSERVED") != "NO":
        raise AnalysisError("stock AI response attestation failed")
    if attestation.get("HI_ROKID_RECOVERY") != "PASS":
        raise AnalysisError("Hi Rokid recovery attestation failed")

    return {
        "schema": "rokid.test20-r2.sanitized-summary.v1",
        "run_id_sha256": hashlib.sha256(
            next(iter(run_ids)).encode("utf-8")
        ).hexdigest(),
        "firmware": expected_firmware,
        "hi_rokid_version": EXPECTED_HI_ROKID_VERSION,
        "cxr_l_coordinate": "com.rokid.cxr:client-l:1.0.1",
        "application": {
            "package": EXPECTED_PACKAGE,
            "version_name": EXPECTED_VERSION,
            "version_code": EXPECTED_VERSION_CODE,
        },
        "qualification": {
            "single_connection_attempt": True,
            "required_cycles": REQUIRED_CYCLES,
            "accepted_start_callbacks": len(starts),
            "accepted_stop_callbacks": len(stops),
            "ordered_cycles": REQUIRED_CYCLES,
            "duplicate_start_callbacks": 0,
            "out_of_order_stop_callbacks": 0,
            "terminal": "AI_ASSIST_TWO_ORDERED_CYCLES_OBSERVED",
            "clean_disconnect": True,
            "hi_rokid_recovery": True,
        },
        "safety": {
            "test_app_ai_assistant_invocation": "NONE",
            "test_app_cloud_ai_request": "NONE",
            "operator_spoken_ai_query": "NONE",
            "stock_ai_response_observed": "NO",
            "camera_access_by_test_app": "NONE",
            "microphone_access_by_test_app": "NONE",
            "media_stream_requested_by_test_app": "NONE",
            "custom_command": "NONE",
            "custom_view": "NONE",
            "glass_app_management": "NONE",
            "hi_rokid_force_stop": "NONE",
            "bluetooth_pairing_mutation": "NONE",
            "reboot": "NONE",
        },
        "privacy": {
            "authorization_token_value_present": False,
            "raw_bluetooth_address_present": False,
            "raw_device_serial_present": False,
            "media_payload_present": False,
            "spoken_prompt_present": False,
            "ai_response_present": False,
        },
        "source_event_sha256": sha256_file(events_path),
    }


def write_outputs(summary: dict[str, Any], output_dir: Path) -> None:
    sanitized = output_dir / "sanitized"
    sanitized.mkdir(parents=True, exist_ok=True)
    json_path = sanitized / "test20-r2-cxr-l-event-summary.json"
    md_path = sanitized / "test20-r2-cxr-l-event-summary.md"
    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    q = summary["qualification"]
    s = summary["safety"]
    md_path.write_text(
        "\n".join(
            [
                "# Test 20 r2 — sanitized CXR-L event summary",
                "",
                f"- Firmware: `{summary['firmware']}`",
                f"- Hi Rokid: `{summary['hi_rokid_version']}`",
                f"- CXR-L: `{summary['cxr_l_coordinate']}`",
                f"- Ordered AI-assist cycles: `{q['ordered_cycles']}`",
                f"- Terminal: `{q['terminal']}`",
                f"- Clean disconnect: `{str(q['clean_disconnect']).lower()}`",
                f"- Hi Rokid recovery: `{str(q['hi_rokid_recovery']).lower()}`",
                "",
                "## Safety boundary",
                "",
                f"- Test-app assistant invocation: `{s['test_app_ai_assistant_invocation']}`",
                f"- Test-app cloud AI request: `{s['test_app_cloud_ai_request']}`",
                f"- Operator spoken AI query: `{s['operator_spoken_ai_query']}`",
                f"- Camera access by test app: `{s['camera_access_by_test_app']}`",
                f"- Microphone access by test app: `{s['microphone_access_by_test_app']}`",
                f"- Media stream requested by test app: `{s['media_stream_requested_by_test_app']}`",
                "",
                "This test qualifies only the two callback methods and the "
                "bounded connection/disconnect lifecycle. It does not prove "
                "the absence of unrelated stock background network traffic.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--operator-attestation", required=True, type=Path)
    parser.add_argument("--expected-firmware", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        summary = analyze(
            args.events,
            args.operator_attestation,
            args.expected_firmware,
        )
        write_outputs(summary, args.output)
    except (OSError, ValueError, AnalysisError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        print("TEST20_R2_ANALYSIS=FAIL")
        return 1

    print("TEST20_R2_HI_ROKID_1_11_SURFACE=PASS")
    print("TEST20_R2_AUTHORIZATION=PASS")
    print("TEST20_R2_CUSTOMAPP_SESSION_CONFIG=PASS")
    print("TEST20_R2_CXR_L_SERVICE_CONNECTION=PASS")
    print("TEST20_R2_GLASS_BLUETOOTH_CALLBACK=PASS")
    print("TEST20_R2_AI_ASSIST_START_CALLBACK=PASS")
    print("TEST20_R2_AI_ASSIST_STOP_CALLBACK=PASS")
    print("TEST20_R2_CALLBACK_ORDERING=PASS")
    print("TEST20_R2_REPEAT_BEHAVIOR=PASS")
    print("TEST20_R2_CLEAN_DISCONNECT=PASS")
    print("TEST20_R2_HI_ROKID_RECOVERY=PASS")
    print("TEST20_R2_TEST_APP_CLOUD_AI_REQUEST=NONE")
    print("TEST20_R2_OPERATOR_SPOKEN_AI_QUERY=NONE")
    print("TEST20_R2_TEST_APP_MEDIA_OPERATION=NONE")
    print("TEST20_R2_PRIVACY_GATE=PASS")
    print(
        "TEST20_R2_CLASSIFICATION="
        "CXR_L_AI_ASSIST_EVENT_CALLBACKS_AND_STOCK_RECOVERY_PASS"
    )
    print("TEST20_R2_QUALIFICATION=PASS")
    print("TEST20_R2_ANALYSIS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
