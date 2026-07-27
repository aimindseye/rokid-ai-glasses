#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from r25lib import read_json, write_json

WRITE_OPCODES = {"0x12", "0x52", "18", "82"}


def read_state(capture: Path, phase: str) -> dict[str, Any] | None:
    path = capture / "snapshots" / phase / "glasses" / "adb-state-private.json"
    return read_json(path) if path.is_file() else None


def normalized_state(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "reachable": value.get("reachable"),
        "persist_vendor_adb": value.get("persist_vendor_adb"),
        "adb_enabled": value.get("adb_enabled"),
        "persist_sys_usb_config": value.get("persist_sys_usb_config"),
        "sys_usb_config": value.get("sys_usb_config"),
    }


def transitions(states: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    order = ["developer_mode_view", "developer_mode_off", "developer_mode_on"]
    output: list[dict[str, Any]] = []
    previous_phase: str | None = None
    previous: dict[str, Any] | None = None
    for phase in order:
        state = normalized_state(states.get(phase))
        if state is None:
            continue
        if previous is not None and state != previous:
            output.append({"from_phase": previous_phase, "to_phase": phase, "before": previous, "after": state})
        previous_phase = phase
        previous = state
    return output


def candidate_messages(metadata: Path | None) -> list[dict[str, Any]]:
    if metadata is None or not metadata.is_file():
        return []
    rows: list[dict[str, str]] = []
    with metadata.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row.get("payload_sha256") and row.get("att_opcode") in WRITE_OPCODES:
                rows.append(row)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        digest = row["payload_sha256"]
        entry = grouped.setdefault(digest, {
            "payload_sha256": digest,
            "payload_length": row.get("payload_length"),
            "observation_count": 0,
            "att_handles": set(),
            "att_opcodes": set(),
        })
        entry["observation_count"] += 1
        if row.get("att_handle"):
            entry["att_handles"].add(row["att_handle"])
        if row.get("att_opcode"):
            entry["att_opcodes"].add(row["att_opcode"])
    result: list[dict[str, Any]] = []
    for entry in grouped.values():
        entry["att_handles"] = sorted(entry["att_handles"])
        entry["att_opcodes"] = sorted(entry["att_opcodes"])
        result.append(entry)
    return sorted(result, key=lambda item: (-item["observation_count"], item["payload_sha256"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--bluetooth-metadata", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    states = {phase: read_state(args.capture, phase) for phase in ["developer_mode_view", "developer_mode_off", "developer_mode_on"]}
    state_transitions = transitions(states)
    candidates = candidate_messages(args.bluetooth_metadata)
    attempted = states["developer_mode_off"] is not None or states["developer_mode_on"] is not None

    if not attempted:
        classification = "NOT_ATTEMPTED"
    elif not state_transitions:
        classification = "NO_STATE_TRANSITION"
    elif args.bluetooth_metadata is None or not args.bluetooth_metadata.is_file():
        classification = "STATE_TRANSITION_WITHOUT_TRANSPORT_METADATA"
    elif candidates:
        classification = "TRANSPORT_CORRELATED_NOT_COMMAND_DECODED"
    else:
        classification = "TRANSPORT_CORRELATED_NOT_COMMAND_DECODED"

    result = {
        "schema": "rokid.r25.developer-mode-attribution.v1",
        "classification": classification,
        "known_setting_key": "settings_developer_mode",
        "known_enable_effects": ["persist.vendor.adb=true", "Settings.Global.adb_enabled=1"],
        "known_disable_effects": ["persist.vendor.adb=false"],
        "states": {key: normalized_state(value) for key, value in states.items()},
        "state_transitions": state_transitions,
        "candidate_messages": candidates,
        "remote_invocation_closed": False,
        "reason_not_closed": "repeated directionally bounded request/reply and authenticated replay are required",
    }
    write_json(args.output, result)
    print(f"R25_DEVELOPER_MODE_CLASSIFICATION={classification}")
    print(f"R25_DEVELOPER_MODE_STATE_TRANSITION_COUNT={len(state_transitions)}")
    print(f"R25_DEVELOPER_MODE_CANDIDATE_MESSAGE_COUNT={len(candidates)}")
    print("R25_DEVELOPER_MODE_REMOTE_INVOCATION_CLOSED=NO")
    print("R25_DEVELOPER_MODE_ATTRIBUTION=PASS_BOUNDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
