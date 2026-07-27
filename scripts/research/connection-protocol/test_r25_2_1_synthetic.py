#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile


def event(event_type, details=None, device_id=None, time_epoch_ms=0):
    row = {
        "event_type": event_type,
        "time_epoch_ms": time_epoch_ms,
        "details": details or {},
    }
    if device_id is not None:
        row["device_id"] = device_id
    return row


def advertisement(phase, elapsed, device_id, structure, payload, rssi=-42):
    return event(
        "r25_2_1_ble_advertisement",
        {
            "phase": phase,
            "phase_elapsed_ms": elapsed,
            "rssi": rssi,
            "connectable": True,
            "payload_fingerprint_sha256": payload,
            "structure_fingerprint_sha256": structure,
            "manufacturer_data_count": 1,
            "service_data_count": 0,
            "manufacturer_data": [
                {
                    "company_id": 4660,
                    "payload_length": 8,
                    "payload_sha256": "11" * 32,
                }
            ],
            "service_data": [],
            "advertised_service_uuids": [],
        },
        device_id=device_id,
        time_epoch_ms=elapsed,
    )


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    analyzer = script_dir / "analyze_r25_2_1_power_state.py"
    verifier = script_dir / "verify_r25_2_1_publication.py"

    rows = [event("client_environment", {"release": "r1.3.3.2.25.2.1"})]
    for phase in ("off_baseline", "power_on_transition", "on_steady"):
        rows.append(event("r25_2_1_phase_started", {"phase": phase}))
        if phase == "off_baseline":
            for index in range(8):
                rows.append(advertisement(
                    phase,
                    1000 + index * 1000,
                    "household-device",
                    "a" * 64,
                    "b" * 64,
                    rssi=-70,
                ))
        else:
            for index in range(8):
                rows.append(advertisement(
                    phase,
                    1000 + index * 1000,
                    "power-correlated-device" if index < 4 else "rotated-device-id",
                    "c" * 64,
                    ("d" if index % 2 == 0 else "e") * 64,
                    rssi=-40,
                ))
            for index in range(5):
                rows.append(advertisement(
                    phase,
                    2000 + index * 1200,
                    "household-device",
                    "a" * 64,
                    "b" * 64,
                    rssi=-70,
                ))
        rows.append(event("r25_2_1_phase_complete", {"phase": phase}))
    rows.append(event("r25_2_1_capture_complete", {"phase_count": 3}))

    metadata = {
        "schema": "rokid.r25.2.1.run-metadata.v1",
        "hi_rokid_disabled_before": True,
        "hi_rokid_running_before": False,
        "hi_rokid_disabled_after": True,
        "hi_rokid_running_after": False,
    }

    with tempfile.TemporaryDirectory() as directory_name:
        directory = Path(directory_name)
        client_log = directory / "client.jsonl"
        metadata_path = directory / "metadata.json"
        private_path = directory / "private.json"
        public_path = directory / "public.json"
        client_log.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
        metadata_path.write_text(json.dumps(metadata) + "\n", encoding="utf-8")

        result = subprocess.run(
            [
                "python3",
                str(analyzer),
                "--client-log",
                str(client_log),
                "--run-metadata",
                str(metadata_path),
                "--private-output",
                str(private_path),
                "--public-output",
                str(public_path),
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        if "R25_2_1_UNIQUE_CANDIDATE_ATTRIBUTED=YES" not in result.stdout:
            raise SystemExit("synthetic unique-candidate gate did not close")
        if "PASS_UNIQUE_BLE_IDENTITY_ATTRIBUTED" not in result.stdout:
            raise SystemExit("synthetic acceptance marker missing")

        subprocess.run(
            [
                "python3",
                str(verifier),
                "--publication",
                str(public_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    print("R1_3_3_2_25_2_1_SYNTHETIC_ANALYSIS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
