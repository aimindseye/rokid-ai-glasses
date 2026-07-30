#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import subprocess
import tempfile


def row(event_type: str, details: dict) -> dict:
    return {"event_type": event_type, "details": details}


def main() -> int:
    root = Path(__file__).resolve().parent
    analyzer = root / "analyze_r25_2_2_1_cached_runtime.py"
    verifier = root / "verify_r25_2_2_1_publication.py"

    address = ":".join(("02", "00", "00", "00", "AA", "BB"))
    runtime_uuid = "89679c22-9cac-464d-86d8-d254bc8b649b"
    key = bytes.fromhex("11" * 32)
    token = hmac.new(key, address.encode("ascii"), hashlib.sha256).hexdigest()

    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        client = base / "client.jsonl"
        metadata = base / "metadata.json"
        logcat = base / "logcat.txt"
        key_file = base / "key.hex"
        private = base / "private.json"
        public = base / "public.json"
        handoff = base / "handoff.json"

        rows = [
            row("r25_2_2_phase_started", {"phase": "stock_disabled_baseline"}),
            row("r25_2_2_phase_complete", {"phase": "stock_disabled_baseline"}),
            row("r25_2_2_phase_started", {"phase": "stock_assist_window"}),
            row("r25_2_2_ble_advertisement", {
                "phase": "stock_assist_window",
                "address_hmac_sha256": token,
                "rssi": -44,
            }),
            row("r25_2_2_phase_complete", {"phase": "stock_assist_window"}),
            row("r25_2_2_phase_started", {"phase": "post_stock_handoff"}),
            row("r25_2_2_phase_complete", {"phase": "post_stock_handoff"}),
            row("r25_2_2_capture_complete", {}),
        ]
        client.write_text(
            "\n".join(json.dumps(value) for value in rows) + "\n",
            encoding="utf-8",
        )
        metadata.write_text(json.dumps({
            "stock_assist_start_epoch": 1785154088,
            "stock_assist_end_epoch": 1785154148,
            "stock_uid": None,
            "stock_pids": [14080],
            "stock_launch_verified": True,
            "stock_foreground_verified": True,
            "stock_enabled_for_assist": True,
            "stock_disabled_after_assist": True,
        }), encoding="utf-8")
        key_file.write_text(key.hex() + "\n", encoding="utf-8")

        lines = [
            f"1785154091.003 14080 14166 I CxrController: connectBluetooth context:x,socketUuid:{runtime_uuid},macAddress:{address}",
            "1785154091.813 2334 2638 I bt_bta_dm: Acl connected peer:xx:xx:xx:xx:AA:BB transport:BT_TRANSPORT_BR_EDR handle:11",
            "1785154091.813 2334 2683 I BluetoothRemoteDevices: BR/EDR Connected XX:XX:XX:XX:AA:BB(Public )",
            "1785154091.878 2334 2638 I bluetooth: service discovery complete bd_addr:xx:xx:xx:xx:AA:BB result:SUCCESS scn:3",
            "1785154091.878 2334 2638 I bt_port_api: RFCOMM_CreateConnectionWithSecurity: bd_addr=xx:xx:xx:xx:AA:BB, scn=3, is_server=false, mtu=990, uuid=0x1101, dlci=6",
            "1785154091.960 2334 2638 I bt_btif_sock_rfcomm: connected to RFCOMM socket connections for device: xx:xx:xx:xx:AA:BB, scn: 3, app_uid: 10305",
            "1785154091.961 14080 14168 I BluetoothSocket: connect(), socket connected. mPort=3",
            "1785154091.961 14080 14168 I BluetoothController: readFromRfcomm",
            "1785154091.961 14080 14268 I BluetoothController: CxrSocketProtocol version:4",
            "1785154091.962 14080 14268 I BluetoothController: mCxrSocketProtocol run end,result:true",
            "1785154091.984 14080 14269 I BluetoothController: updateStatus status:BLUETOOTH_AVAILABLE,errorCode:SUCCEED",
        ]
        logcat.write_text("\n".join(lines) + "\n", encoding="utf-8")

        subprocess.run([
            "python3", str(analyzer),
            "--client-log", str(client),
            "--stock-logcat", str(logcat),
            "--run-metadata", str(metadata),
            "--correlation-key", str(key_file),
            "--private-output", str(private),
            "--public-output", str(public),
            "--handoff-output", str(handoff),
        ], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(
            ["python3", str(verifier), "--publication", str(public)],
            check=True,
            stdout=subprocess.DEVNULL,
        )

        private_value = json.loads(private.read_text(encoding="utf-8"))
        public_value = json.loads(public.read_text(encoding="utf-8"))
        handoff_value = json.loads(handoff.read_text(encoding="utf-8"))
        assert private_value["stock_uid"] == 10305
        assert private_value["candidate_count"] == 1
        assert private_value["qualifying_candidate_count"] == 1
        assert private_value["unique_runtime_endpoint_attributed"] is True
        assert public_value["runtime_address_published"] is False
        assert public_value["runtime_uuid_published"] is False
        assert handoff_value["runtime_address"] == address
        assert handoff_value["runtime_uuid"] == runtime_uuid
        assert handoff_value["rfcomm"] == {
            "client": True,
            "dlci": 6,
            "mtu": 990,
            "scn": 3,
            "uuid16": "0x1101",
        }
        assert handoff_value[
            "ready_for_independent_connection_only_qualification"
        ] is True

    print("R25_2_2_1_SYNTHETIC_UNIQUE_ENDPOINT=PASS")
    print("R25_2_2_1_SYNTHETIC_UID_INFERENCE=PASS")
    print("R25_2_2_1_SYNTHETIC_PUBLICATION_SANITIZATION=PASS")
    print("R25_2_2_1_SYNTHETIC_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
