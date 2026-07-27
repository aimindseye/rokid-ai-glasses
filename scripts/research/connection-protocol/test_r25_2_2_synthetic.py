#!/usr/bin/env python3
import hashlib
import hmac
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    key = bytes(range(32))
    address = "AA:BB:CC:DD:EE:FF"
    token = hmac.new(key, address.encode("ascii"), hashlib.sha256).hexdigest()

    rows = []
    for phase in (
        "stock_disabled_baseline",
        "stock_assist_window",
        "post_stock_handoff",
    ):
        rows.append({"event_type": "r25_2_2_phase_started", "details": {"phase": phase}})
        if phase != "stock_disabled_baseline":
            rows.append(
                {
                    "event_type": "r25_2_2_ble_advertisement",
                    "details": {
                        "phase": phase,
                        "address_hmac_sha256": token,
                        "rssi": -42,
                        "structure_fingerprint_sha256": "1" * 64,
                        "payload_fingerprint_sha256": "2" * 64,
                        "advertised_service_uuids": [],
                    },
                }
            )
        rows.append({"event_type": "r25_2_2_phase_complete", "details": {"phase": phase}})
    rows.append({"event_type": "r25_2_2_capture_complete", "details": {}})

    (root / "client.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    (root / "key.hex").write_text(key.hex() + "\n", encoding="utf-8")
    (root / "stock.log").write_text(
        "1780000000.000 10305 111 111 I BluetoothGatt: "
        f"com.rokid.sprite.global.aiapp connect() - device: {address}\n"
        "1780000002.000 1002 222 222 I BluetoothController: "
        "handleGattCharacteristicRead uuid:00009301-0000-1000-8000-00805f9b34fb "
        f"device {address}\n",
        encoding="utf-8",
    )
    (root / "metadata.json").write_text(
        json.dumps(
            {
                "stock_pids": [111],
                "stock_launcher_component": (
                    "com.rokid.sprite.global.aiapp/"
                    "com.rokid.sprite.aiapp.ui.SplashActivity"
                ),
                "stock_launch_verified": True,
                "stock_foreground_verified": True,
                "stock_enabled_for_assist": True,
                "stock_disabled_after_assist": True,
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(HERE / "analyze_r25_2_2_stock_assist.py"),
            "--client-log",
            str(root / "client.jsonl"),
            "--stock-logcat",
            str(root / "stock.log"),
            "--correlation-key",
            str(root / "key.hex"),
            "--run-metadata",
            str(root / "metadata.json"),
            "--private-output",
            str(root / "private.json"),
            "--public-output",
            str(root / "public.json"),
            "--handoff-output",
            str(root / "handoff.json"),
        ],
        check=True,
    )

    publication = json.loads((root / "public.json").read_text(encoding="utf-8"))
    assert publication["acceptance"] == "PASS_UNIQUE_PROVISIONING_GATT_ENDPOINT_CORRELATED"
    assert publication["endpoint_address_published"] is False
    assert address not in (root / "public.json").read_text(encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(HERE / "verify_r25_2_2_publication.py"),
            "--publication",
            str(root / "public.json"),
        ],
        check=True,
    )

print("R25_2_2_SYNTHETIC_ANALYSIS=PASS")
