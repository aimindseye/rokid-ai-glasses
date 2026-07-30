#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile


def event(event_type: str, details: dict) -> dict:
    return {
        "schema": "rokid.r25.client-event.v1",
        "time_epoch_ms": 1000,
        "event_type": event_type,
        "run_id": "synthetic",
        "device_id": "dev-synthetic",
        "details": details,
    }


def main() -> int:
    root = Path(__file__).resolve().parent
    analyzer = root / "analyze_r25_2_2_2_connection_only.py"
    verifier = root / "verify_r25_2_2_2_publication.py"
    address = ":".join(("02", "00", "00", "00", "00", "02"))
    runtime_uuid = "12345678-1234-4234-9234-123456789abc"
    import hashlib
    sha = lambda value: hashlib.sha256(value.encode()).hexdigest()

    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        handoff = {
            "schema": "rokid.r25.2.2.2.connection-only-input-private.v1",
            "runtime_address": address,
            "runtime_address_sha256": sha(address),
            "runtime_uuid": runtime_uuid,
            "runtime_uuid_sha256": sha(runtime_uuid),
            "endpoint_binding_sha256": sha(address + "|" + runtime_uuid),
            "expected_rfcomm": {"client": True, "scn": 3, "dlci": 6, "mtu": 990},
            "ready_for_independent_connection_only_qualification": True,
            "application_payload_operation_authorized": False,
        }
        handoff_path = base / "handoff.json"
        handoff_path.write_text(json.dumps(handoff))
        common = {
            "runtime_address_sha256": sha(address),
            "runtime_address_published": False,
            "runtime_uuid_sha256": sha(runtime_uuid),
            "runtime_uuid_published": False,
            "endpoint_binding_sha256": sha(address + "|" + runtime_uuid),
            "source_private_zip_sha256": "1" * 64,
            "source_handoff_sha256": "2" * 64,
            "expected_scn": 3,
            "expected_dlci": 6,
            "expected_mtu": 990,
            "application_payload_operation_authorized": False,
        }
        rows = [
            event("client_environment", {
                "mode": "private_handoff_rfcomm_connection_only",
                "gatt_available_in_ui": False,
                "application_payload_read_implemented": False,
                "application_payload_write_implemented": False,
            }),
            event("r25_2_2_2_handoff_loaded", common),
            event("r25_2_2_2_rfcomm_connect_requested", {
                **common,
                "application_payload_read_count": 0,
                "application_payload_write_count": 0,
                "application_data_streams_obtained": False,
            }),
            event("r25_2_2_2_rfcomm_socket_open", {
                **common,
                "connected": True,
                "max_receive_packet_size": 990,
                "max_transmit_packet_size": 990,
                "application_payload_read_count": 0,
                "application_payload_write_count": 0,
                "application_data_streams_obtained": False,
            }),
            event("r25_2_2_2_rfcomm_socket_closed", {
                **common,
                "socket_had_opened": True,
                "application_payload_read_count": 0,
                "application_payload_write_count": 0,
                "application_data_streams_obtained": False,
            }),
        ]
        client = base / "client.jsonl"
        client.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        logcat = base / "logcat.txt"
        logcat.write_text(
            f"1000.0 111 222 I btif: {address} RFCOMM client app_uid: 10320 scn: 3 dlci: 6 mtu: 990\n"
            f"1000.1 111 222 I BluetoothSocket: {address} connected mPort=3\n"
        )
        metadata = base / "metadata.json"
        metadata.write_text(json.dumps({
            "probe_uid": 10320,
            "probe_pids": [111],
            "stock_package_disabled": True,
            "stock_pid_observed": False,
        }))
        private = base / "private.json"
        public = base / "public.json"
        subprocess.run([
            "python3", str(analyzer),
            "--client-log", str(client),
            "--phone-logcat", str(logcat),
            "--metadata", str(metadata),
            "--input-handoff", str(handoff_path),
            "--private-output", str(private),
            "--public-output", str(public),
        ], check=True)
        value = json.loads(private.read_text())
        assert value["acceptance"] == (
            "PASS_PRIVATE_HANDOFF_RFCOMM_SOCKET_OPEN_"
            "SCN3_DLCI6_MTU990_ZERO_PAYLOAD_CLOSED"
        )
        subprocess.run(["python3", str(verifier), "--publication", str(public)], check=True)

    print("R25_2_2_2_SYNTHETIC_SOCKET_OPEN=PASS")
    print("R25_2_2_2_SYNTHETIC_SCN3_DLCI6_MTU990=PASS")
    print("R25_2_2_2_SYNTHETIC_ZERO_PAYLOAD=PASS")
    print("R25_2_2_2_SYNTHETIC_PUBLICATION=PASS")
    print("R25_2_2_2_SYNTHETIC_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
