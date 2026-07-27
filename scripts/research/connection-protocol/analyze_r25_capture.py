#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from r25lib import read_json, write_json


def invoke(command: list[str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--client-log", type=Path)
    args = parser.parse_args()

    capture = args.capture.expanduser().resolve()
    analysis = capture / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent

    bugreport = capture / "phone-bugreport-private.zip"
    hci = capture / "bluetooth-hci-private.log"
    metadata = analysis / "bluetooth-metadata-private.tsv"
    if bugreport.is_file() and not hci.is_file():
        completed = subprocess.run([sys.executable, str(here / "extract_bluetooth_snoop.py"), "--bugreport", str(bugreport), "--output", str(hci)])
        if completed.returncode not in {0, 2}:
            raise SystemExit(completed.returncode)
    if hci.is_file():
        completed = subprocess.run([sys.executable, str(here / "extract_bluetooth_metadata.py"), "--pcap", str(hci), "--output", str(metadata)])
        if completed.returncode == 3:
            print("R25_BLUETOOTH_METADATA=SKIPPED_TSHARK_UNAVAILABLE")
        elif completed.returncode != 0:
            raise SystemExit(completed.returncode)

    client_summary = analysis / "client-probe-summary-private.json"
    if args.client_log:
        invoke([sys.executable, str(here / "analyze_client_probe.py"), "--client-log", str(args.client_log), "--output", str(client_summary)])

    pairing_summary = analysis / "pairing-channel-summary-private.json"
    pairing_command = [sys.executable, str(here / "analyze_pairing_channel.py"), "--capture", str(capture), "--output", str(pairing_summary)]
    if metadata.is_file():
        pairing_command += ["--bluetooth-metadata", str(metadata)]
    if client_summary.is_file():
        pairing_command += ["--client-summary", str(client_summary)]
    invoke(pairing_command)

    developer_summary = analysis / "developer-mode-attribution-private.json"
    developer_command = [sys.executable, str(here / "analyze_developer_mode_attribution.py"), "--capture", str(capture), "--output", str(developer_summary)]
    if metadata.is_file():
        developer_command += ["--bluetooth-metadata", str(metadata)]
    invoke(developer_command)

    pairing = read_json(pairing_summary)
    developer = read_json(developer_summary)
    client = read_json(client_summary) if client_summary.is_file() else {
        "event_count": 0,
        "gatt_service_uuids": [],
        "sdp_uuids": [],
        "write_events": 0,
    }
    summary = {
        "schema": "rokid.r25.capture-summary.v1",
        "pairing_channel": pairing,
        "developer_mode": developer,
        "client_probe": client,
        "live_closure": {
            "stock_pairing_channel_closed": False,
            "developer_mode_remote_invocation_closed": developer.get("classification") == "REMOTE_INVOCATION_CLOSED",
            "minimal_client_stock_session_qualified": False,
            "minimal_client_read_only_inventory_present": bool(client.get("gatt_service_uuids") or client.get("sdp_uuids")),
        },
    }
    write_json(analysis / "r25-summary-private.json", summary)
    print("R1_3_3_2_25_CAPTURE_ANALYSIS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
