#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from r25lib import read_json, write_json


def read_timeline(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return sorted(rows, key=lambda item: item["time_epoch_ns"])


def phase_windows(timeline: list[dict[str, Any]]) -> list[tuple[str, float, float]]:
    action_starts: dict[str, float] = {}
    windows: list[tuple[str, float, float]] = []
    for row in timeline:
        phase = row.get("phase")
        event = row.get("event")
        ts = row["time_epoch_ns"] / 1_000_000_000
        if event == "operator_action_start":
            action_starts[phase] = ts
        elif event == "operator_action_complete" and phase in action_starts:
            windows.append((phase, action_starts.pop(phase), ts + 3.0))
    return windows


def assign_phase(epoch: float, windows: list[tuple[str, float, float]]) -> str:
    for phase, start, end in windows:
        if start <= epoch <= end:
            return phase
    return "outside_operator_window"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--bluetooth-metadata", type=Path)
    parser.add_argument("--client-summary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    timeline = read_timeline(args.capture / "timeline-private.ndjson")
    windows = phase_windows(timeline)
    transport_counts: Counter[str] = Counter()
    phase_counts: dict[str, Counter[str]] = defaultdict(Counter)
    att_handles: set[str] = set()
    gatt_uuids: set[str] = set()
    l2cap_psms: set[str] = set()
    rfcomm_channels: set[str] = set()
    sdp_uuids: set[str] = set()
    payload_hashes: Counter[str] = Counter()

    metadata_present = bool(args.bluetooth_metadata and args.bluetooth_metadata.is_file())
    if metadata_present:
        with args.bluetooth_metadata.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                epoch_raw = row.get("time_epoch", "")
                try:
                    phase = assign_phase(float(epoch_raw), windows)
                except ValueError:
                    phase = "unknown_time"
                if row.get("att_opcode"):
                    transport_counts["ATT"] += 1
                    phase_counts[phase]["ATT"] += 1
                if row.get("rfcomm_channel"):
                    transport_counts["RFCOMM"] += 1
                    phase_counts[phase]["RFCOMM"] += 1
                    rfcomm_channels.add(row["rfcomm_channel"])
                if row.get("sdp_uuid"):
                    transport_counts["SDP"] += 1
                    phase_counts[phase]["SDP"] += 1
                    sdp_uuids.update(item for item in row["sdp_uuid"].split(",") if item)
                if row.get("l2cap_cid") or row.get("l2cap_psm"):
                    transport_counts["L2CAP"] += 1
                    phase_counts[phase]["L2CAP"] += 1
                if row.get("att_handle"):
                    att_handles.add(row["att_handle"])
                if row.get("att_uuid16"):
                    gatt_uuids.update(item for item in row["att_uuid16"].split(",") if item)
                if row.get("att_uuid128"):
                    gatt_uuids.update(item for item in row["att_uuid128"].split(",") if item)
                if row.get("l2cap_psm"):
                    l2cap_psms.update(item for item in row["l2cap_psm"].split(",") if item)
                if row.get("payload_sha256"):
                    payload_hashes[row["payload_sha256"]] += 1

    client = read_json(args.client_summary) if args.client_summary and args.client_summary.is_file() else None
    if client:
        gatt_uuids.update(client.get("gatt_service_uuids", []))
        sdp_uuids.update(client.get("sdp_uuids", []))

    pairing_events = phase_counts.get("pairing_or_reconnect", Counter())
    if not metadata_present and not client:
        status = "NO_TRANSPORT_METADATA"
    elif pairing_events:
        status = "STOCK_ACTION_TRANSPORT_OBSERVED"
    elif client and (client.get("gatt_service_uuids") or client.get("sdp_uuids")):
        status = "READ_ONLY_CLIENT_BOUNDARY_OBSERVED"
    else:
        status = "TRANSPORT_METADATA_PRESENT_NO_PAIRING_WINDOW_ACTIVITY"

    result = {
        "schema": "rokid.r25.pairing-channel-summary.v1",
        "status": status,
        "known_static_boundary": {
            "endpoint": "CXRControl",
            "operation": "startBTPairing",
            "argument_shape": "one unsigned integer",
        },
        "operator_windows": [
            {"phase": phase, "start_epoch": start, "end_epoch": end}
            for phase, start, end in windows
        ],
        "transport_counts": dict(sorted(transport_counts.items())),
        "phase_transport_counts": {phase: dict(sorted(counts.items())) for phase, counts in sorted(phase_counts.items())},
        "att_handles": sorted(att_handles),
        "gatt_uuids": sorted(gatt_uuids),
        "l2cap_psms": sorted(l2cap_psms),
        "rfcomm_channels": sorted(rfcomm_channels),
        "sdp_uuids": sorted(sdp_uuids),
        "payload_hash_counts": dict(sorted(payload_hashes.items())),
        "client_probe_present": client is not None,
        "session_authentication_contract": "UNRESOLVED",
        "message_framing_contract": "UNRESOLVED",
        "independent_stock_session_implemented": False,
    }
    write_json(args.output, result)
    print(f"R25_PAIRING_CHANNEL_STATUS={status}")
    print(f"R25_PAIRING_ATT_COUNT={pairing_events.get('ATT', 0)}")
    print(f"R25_PAIRING_RFCOMM_COUNT={pairing_events.get('RFCOMM', 0)}")
    print(f"R25_PAIRING_GATT_UUID_COUNT={len(gatt_uuids)}")
    print("R25_STOCK_SESSION_IMPLEMENTED=NO")
    print("R25_PAIRING_CHANNEL_ANALYSIS=PASS_BOUNDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
