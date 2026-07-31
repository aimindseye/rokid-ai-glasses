#!/usr/bin/env python3
"""Analyze one Test 19 r2 CXR-L connection-only run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "rokid.test19-r2.cxrl-event.v1"
EXPECTED_HI_ROKID_VERSION = "G1.11.11.0727"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"malformed JSONL at line {line_number}: {error}") from error
        if isinstance(value, dict) and value.get("schema") == SCHEMA:
            records.append(value)
    return records


def event(records: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [item for item in records if item.get("event_type") == event_type]


def detail_any(records: list[dict[str, Any]], event_type: str, key: str, expected: Any) -> bool:
    return any(item.get("details", {}).get(key) == expected for item in event(records, event_type))


def host_recovery(path: Path | None) -> bool | None:
    if path is None or not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value.get("hi_rokid_recovery_confirmed") is True


def analyze(records: list[dict[str, Any]], recovery: bool | None) -> dict[str, Any]:
    environments = event(records, "hi_rokid_environment")
    environment_pass = any(
        item.get("details", {}).get("package_name") == "com.rokid.sprite.global.aiapp"
        and item.get("details", {}).get("version_name") == EXPECTED_HI_ROKID_VERSION
        and item.get("details", {}).get("authorization_resolved") is True
        and item.get("details", {}).get("media_service_resolved") is True
        for item in environments
    )
    auth_pass = detail_any(records, "authorization_result", "token_present", True)
    config_pass = detail_any(records, "session_config_result", "configured", True)
    cxrl_pass = detail_any(records, "callback_cxrl_connected", "connected", True)
    glass_pass = detail_any(records, "callback_glass_bt_connected", "connected", True)
    terminal_pass = any(
        item.get("details", {}).get("outcome") == "CONNECTED_BOTH_CALLBACKS"
        and item.get("details", {}).get("success") is True
        for item in event(records, "qualification_terminal")
    )
    disconnect_pass = any(
        item.get("details", {}).get("sdk_disconnect_returned") is True
        for item in event(records, "disconnect_result")
    )
    completed = bool(event(records, "run_completed"))

    markers = {
        "TEST19_R2_HI_ROKID_1_11_SURFACE": "PASS" if environment_pass else "FAIL",
        "TEST19_R2_AUTHORIZATION": "PASS" if auth_pass else "FAIL",
        "TEST19_R2_CUSTOMAPP_SESSION_CONFIG": "PASS" if config_pass else "BLOCKED" if not auth_pass else "FAIL",
        "TEST19_R2_CXR_L_SERVICE_CONNECTION": "PASS" if cxrl_pass else "BLOCKED" if not config_pass else "FAIL",
        "TEST19_R2_GLASS_BLUETOOTH_CALLBACK": "PASS" if glass_pass else "BLOCKED" if not config_pass else "FAIL",
        "TEST19_R2_CLEAN_DISCONNECT": "PASS" if disconnect_pass else "BLOCKED" if not terminal_pass else "FAIL",
        "TEST19_R2_HI_ROKID_RECOVERY": "PASS" if recovery is True else "FAIL" if recovery is False else "BLOCKED",
    }
    connection_pass = all((environment_pass, auth_pass, config_pass, cxrl_pass, glass_pass, terminal_pass, disconnect_pass, completed))
    qualification_pass = connection_pass and recovery is True

    if qualification_pass:
        exit_code = 0
        classification = "CXR_L_CONNECTION_AND_STOCK_RECOVERY_PASS"
    elif recovery is False:
        exit_code = 20
        classification = "CXR_L_RUN_COMPLETED_BUT_STOCK_RECOVERY_FAILED"
    elif not records or not completed or recovery is None:
        exit_code = 30
        classification = "INCOMPLETE_EVIDENCE"
    else:
        exit_code = 10
        terminal = event(records, "qualification_terminal")
        outcome = terminal[-1].get("details", {}).get("outcome", "UNRESOLVED") if terminal else "UNRESOLVED"
        classification = f"BOUNDED_CXR_L_FAILURE_{outcome}"

    run_ids = sorted({str(item.get("run_id", "")) for item in records if item.get("run_id")})
    firmware_labels = sorted({str(item.get("firmware_label", "")) for item in records if item.get("firmware_label")})
    return {
        "schema": "rokid.test19-r2.cxrl-summary.v1",
        "classification": classification,
        "exit_code": exit_code,
        "qualification_pass": qualification_pass,
        "connection_pass": connection_pass,
        "run_ids": run_ids,
        "firmware_labels": firmware_labels,
        "event_count": len(records),
        "markers": markers,
        "privacy": {
            "authorization_token_value_present": False,
            "raw_bluetooth_address_present": False,
            "media_payload_present": False,
        },
    }


def markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Test 19 r2 CXR-L Connection Summary",
        "",
        f"- Classification: `{summary['classification']}`",
        f"- Qualification pass: `{str(summary['qualification_pass']).lower()}`",
        f"- Firmware labels: `{', '.join(summary['firmware_labels'])}`",
        f"- Event count: `{summary['event_count']}`",
        "",
        "## Markers",
        "",
    ]
    lines.extend(f"- `{key}={value}`" for key, value in summary["markers"].items())
    lines.extend([
        "",
        "The summary excludes authorization-token values, raw Bluetooth addresses, and media payloads.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True)
    parser.add_argument("--host-recovery")
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    try:
        records = load_jsonl(Path(args.events))
        recovery = host_recovery(Path(args.host_recovery)) if args.host_recovery else None
        summary = analyze(records, recovery)
    except Exception as error:  # noqa: BLE001
        print("TEST19_R2_ANALYSIS=FAIL")
        print(f"ERROR={error}")
        return 30

    Path(args.summary_json).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.summary_md).write_text(markdown(summary), encoding="utf-8")
    for key, value in summary["markers"].items():
        print(f"{key}={value}")
    print(f"TEST19_R2_CLASSIFICATION={summary['classification']}")
    print("TEST19_R2_QUALIFICATION=" + ("PASS" if summary["qualification_pass"] else "INCOMPLETE"))
    return int(summary["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
