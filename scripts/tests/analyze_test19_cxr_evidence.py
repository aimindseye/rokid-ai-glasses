#!/usr/bin/env python3
"""Analyze private Test 19 CXR-M evidence into a sanitized qualification summary."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

APP_SCHEMA = "rokid.test19.cxr-client-event.v1"
PHASES = (
    "baseline_stock_connected",
    "stock_background",
    "stock_force_stopped",
    "custom_only",
    "glasses_reboot_reconnect",
    "phone_reboot_reconnect",
    "stock_recovery",
)


def load_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"ERROR: malformed JSONL: {path}:{line_no}: {exc}") from exc
            if isinstance(value, dict):
                value["_source"] = path.relative_to(root).as_posix()
                records.append(value)
    return records


def events(records: Iterable[dict[str, Any]], event_type: str, phase: str | None = None) -> list[dict[str, Any]]:
    return [
        item
        for item in records
        if item.get("schema") == APP_SCHEMA
        and item.get("event_type") == event_type
        and (phase is None or item.get("phase") == phase)
    ]


def any_detail(records: Iterable[dict[str, Any]], event_type: str, key: str, expected: Any) -> bool:
    return any(item.get("details", {}).get(key) == expected for item in events(records, event_type))


def status(passed: bool, failed: bool, blocked: bool = False) -> str:
    if passed:
        return "PASS"
    if failed:
        return "FAIL"
    if blocked:
        return "BLOCKED"
    return "NOT_RUN"


def phase_connected(records: list[dict[str, Any]], phase: str) -> bool:
    return bool(events(records, "cxr_connected", phase))


def phase_failed(records: list[dict[str, Any]], phase: str) -> bool:
    return bool(events(records, "cxr_failed", phase) + events(records, "cxr_connect_failed", phase))


def analyze(records: list[dict[str, Any]]) -> dict[str, Any]:
    app_records = [item for item in records if item.get("schema") == APP_SCHEMA]
    sdk_inventory = events(app_records, "sdk_inventory")
    sdk_present = any(item.get("details", {}).get("sdk_class_found") is True for item in sdk_inventory)
    sdk_init_surface = any(item.get("details", {}).get("init_bluetooth_found") is True for item in sdk_inventory)
    sdk_deinit_surface = any(item.get("details", {}).get("deinit_bluetooth_found") is True for item in sdk_inventory)
    sdk_status_surface = any(int(item.get("details", {}).get("safe_status_method_count", 0)) > 0 for item in sdk_inventory)
    sdk_failed = bool(sdk_inventory) and not (sdk_present and sdk_init_surface and sdk_deinit_surface and sdk_status_surface)

    likely_candidates = [
        item
        for item in events(app_records, "candidate_discovered")
        if item.get("details", {}).get("likely_rokid") is True
    ]
    discovery_failed = bool(events(app_records, "discovery_failed"))

    connected_any = bool(events(app_records, "cxr_connected"))
    connection_failed = bool(events(app_records, "cxr_failed") + events(app_records, "cxr_connect_failed"))

    status_queries = events(app_records, "hardware_status_query_completed")
    hardware_status_pass = any(item.get("details", {}).get("qualified") is True for item in status_queries)
    hardware_status_failed = bool(status_queries) and not hardware_status_pass

    disconnect_pass = bool(events(app_records, "cxr_disconnect_returned") or events(app_records, "cxr_disconnected"))
    disconnect_failed = bool(events(app_records, "cxr_disconnect_failed"))

    phase_results: dict[str, dict[str, Any]] = {}
    for phase in PHASES:
        phase_events = [item for item in app_records if item.get("phase") == phase]
        phase_results[phase] = {
            "event_count": len(phase_events),
            "connected": phase_connected(app_records, phase),
            "failed": phase_failed(app_records, phase),
            "disconnect_returned": bool(events(app_records, "cxr_disconnect_returned", phase)),
            "status_qualified": any(
                item.get("details", {}).get("qualified") is True
                for item in events(app_records, "hardware_status_query_completed", phase)
            ),
        }

    baseline_shared = phase_results["baseline_stock_connected"]["connected"]
    background_shared = phase_results["stock_background"]["connected"]
    force_stop_acquired = phase_results["stock_force_stopped"]["connected"]
    custom_only_acquired = phase_results["custom_only"]["connected"]

    if baseline_shared:
        ownership = "SHARED_WITH_HI_ROKID_FOREGROUND"
    elif background_shared:
        ownership = "SHARED_ONLY_WHEN_HI_ROKID_BACKGROUNDED"
    elif force_stop_acquired:
        ownership = "HI_ROKID_FORCE_STOP_REQUIRED"
    elif custom_only_acquired:
        ownership = "CUSTOM_APP_EXCLUSIVE_OR_STOCK_STATE_UNRESOLVED"
    elif any(phase_results[item]["failed"] for item in PHASES[:4]):
        ownership = "CXR_CONNECTION_REJECTED_IN_TESTED_OWNERSHIP_STATES"
    else:
        ownership = "UNRESOLVED_INCOMPLETE_EVIDENCE"

    reconnect_glasses = phase_results["glasses_reboot_reconnect"]["connected"]
    reconnect_phone = phase_results["phone_reboot_reconnect"]["connected"]
    stock_recovery = phase_results["stock_recovery"]["connected"] or bool(
        events(app_records, "stock_recovery_confirmed", "stock_recovery")
    )

    host_types = {str(item.get("event_type", "")) for item in records if item.get("schema") == "rokid.test19.host-event.v1"}
    privacy_pass = "network_privacy_gate_pass" in host_types
    privacy_fail = "network_privacy_gate_fail" in host_types
    privacy_missing = "network_privacy_gate_missing" in host_types

    markers = {
        "CUSTOM_APP_CXR_M_ARTIFACT_AND_API_SURFACE": status(
            sdk_present and sdk_init_surface and sdk_deinit_surface and sdk_status_surface,
            sdk_failed,
            blocked=not sdk_inventory,
        ),
        "CUSTOM_APP_DEVICE_DISCOVERY": status(bool(likely_candidates), discovery_failed),
        "CUSTOM_APP_DEVICE_CONNECTION": status(connected_any, connection_failed, blocked=not sdk_present),
        "CUSTOM_APP_HARDWARE_STATUS_QUERY": status(
            hardware_status_pass,
            hardware_status_failed,
            blocked=not connected_any,
        ),
        "CUSTOM_APP_CLEAN_DISCONNECT": status(
            disconnect_pass,
            disconnect_failed,
            blocked=not connected_any,
        ),
        "CUSTOM_APP_RECONNECT_AFTER_GLASSES_REBOOT": status(
            reconnect_glasses,
            phase_results["glasses_reboot_reconnect"]["failed"],
            blocked=not connected_any,
        ),
        "CUSTOM_APP_RECONNECT_AFTER_PHONE_REBOOT": status(
            reconnect_phone,
            phase_results["phone_reboot_reconnect"]["failed"],
            blocked=not connected_any,
        ),
        "HI_ROKID_STOCK_RECOVERY": status(
            stock_recovery,
            False,
            blocked=phase_results["stock_recovery"]["event_count"] == 0,
        ),
        "LOCAL_NETWORK_PRIVACY_GATE": status(
            privacy_pass,
            privacy_fail,
            blocked=privacy_missing or not (privacy_pass or privacy_fail),
        ),
    }

    core_names = (
        "CUSTOM_APP_CXR_M_ARTIFACT_AND_API_SURFACE",
        "CUSTOM_APP_DEVICE_DISCOVERY",
        "CUSTOM_APP_DEVICE_CONNECTION",
        "CUSTOM_APP_HARDWARE_STATUS_QUERY",
        "CUSTOM_APP_CLEAN_DISCONNECT",
        "CUSTOM_APP_RECONNECT_AFTER_GLASSES_REBOOT",
        "CUSTOM_APP_RECONNECT_AFTER_PHONE_REBOOT",
        "HI_ROKID_STOCK_RECOVERY",
        "LOCAL_NETWORK_PRIVACY_GATE",
    )
    core_pass = all(markers[name] == "PASS" for name in core_names)

    if not sdk_inventory:
        classification = "CXR_M_SDK_ARTIFACT_NOT_QUALIFIED"
    elif sdk_failed:
        classification = "CXR_M_API_SURFACE_INCOMPATIBLE_OR_ARTIFACT_INVALID"
    elif core_pass and baseline_shared:
        classification = "CXR_M_COMPATIBLE_SHARED_OWNERSHIP"
    elif core_pass and force_stop_acquired and not (baseline_shared or background_shared):
        classification = "CXR_M_COMPATIBLE_HI_ROKID_FORCE_STOP_REQUIRED"
    elif core_pass:
        classification = "CXR_M_COMPATIBLE_OWNERSHIP_PARTIALLY_RESOLVED"
    elif connected_any:
        classification = "CXR_M_CONNECTION_PROVEN_QUALIFICATION_INCOMPLETE"
    elif connection_failed:
        classification = "CXR_M_CONNECTION_REJECTED_ON_TESTED_UNIT_OR_OWNERSHIP_STATE"
    else:
        classification = "UNRESOLVED_INCOMPLETE_EVIDENCE"

    return {
        "schema": "rokid.test19-r1.cxr-qualification-summary.v1",
        "app_event_count": len(app_records),
        "run_count": len({item.get("run_id") for item in app_records if item.get("run_id")}),
        "likely_candidate_count": len(likely_candidates),
        "ownership_classification": ownership,
        "final_classification": classification,
        "qualification_complete": core_pass,
        "markers": markers,
        "phase_results": phase_results,
        "privacy": {
            "raw_bluetooth_addresses_in_summary": False,
            "sdk_artifact_bytes_in_summary": False,
            "credential_values_in_summary": False,
            "public_network_destinations_allowed": False,
        },
    }


def markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Test 19 r1 CXR-M Qualification Summary",
        "",
        f"- Final classification: `{summary['final_classification']}`",
        f"- Ownership classification: `{summary['ownership_classification']}`",
        f"- Qualification complete: `{str(summary['qualification_complete']).lower()}`",
        f"- App events: `{summary['app_event_count']}`",
        f"- App runs: `{summary['run_count']}`",
        "",
        "## Terminal markers",
        "",
    ]
    for name, value in summary["markers"].items():
        lines.append(f"- `{name}={value}`")
    lines.extend(["", "## Ownership phases", ""])
    lines.append("| Phase | Connected | Failed | Status qualified | Disconnect returned |")
    lines.append("|---|---:|---:|---:|---:|")
    for phase, values in summary["phase_results"].items():
        lines.append(
            f"| `{phase}` | {values['connected']} | {values['failed']} | "
            f"{values['status_qualified']} | {values['disconnect_returned']} |"
        )
    lines.extend(
        [
            "",
            "This summary intentionally omits raw Bluetooth addresses, SDK artifact bytes, and private network evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args()

    records = load_records(Path(args.evidence_root))
    summary = analyze(records)
    Path(args.summary_json).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(args.summary_md).write_text(markdown(summary), encoding="utf-8")

    for name, value in summary["markers"].items():
        print(f"{name}={value}")
    print(f"TEST19_R1_OWNERSHIP_CLASSIFICATION={summary['ownership_classification']}")
    print(f"TEST19_R1_FINAL_CLASSIFICATION={summary['final_classification']}")
    print(
        "TEST19_R1_CXR_M_QUALIFICATION="
        + ("PASS" if summary["qualification_complete"] else "INCOMPLETE")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
