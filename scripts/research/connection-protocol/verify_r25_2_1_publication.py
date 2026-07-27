#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FORBIDDEN_KEYS = {
    "device_id",
    "device_ids",
    "fingerprint_sha256",
    "payload_fingerprints",
    "selected_candidate",
    "raw_record_sha256",
    "manufacturer_data",
    "service_data",
    "phone_serial",
    "probe_uid",
}

HEX_ADDRESS = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")
HEX_64 = re.compile(r"(?i)\b[0-9a-f]{64}\b")


def walk(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key, child
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", required=True, type=Path)
    args = parser.parse_args()

    path = args.publication.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"ERROR: publication not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("ERROR: publication is not a JSON object")

    if data.get("schema") != "rokid.r25.2.1.publication.v1":
        raise SystemExit("ERROR: unexpected publication schema")
    if data.get("release") != "r1.3.3.2.25.2.1":
        raise SystemExit("ERROR: unexpected release")

    for parent, key, value in walk(data):
        if key in FORBIDDEN_KEYS:
            raise SystemExit(f"ERROR: forbidden key {parent}.{key}")
        if isinstance(value, str):
            if HEX_ADDRESS.search(value):
                raise SystemExit(f"ERROR: Bluetooth address pattern at {parent}.{key}")
            if HEX_64.search(value):
                raise SystemExit(f"ERROR: private 64-hex fingerprint at {parent}.{key}")

    required_false = (
        "private_device_ids_published",
        "private_fingerprint_hashes_published",
        "raw_advertisement_bytes_published",
        "raw_bluetooth_addresses_published",
    )
    for key in required_false:
        if data.get(key) is not False:
            raise SystemExit(f"ERROR: {key} must be false")

    capture = data.get("capture_model")
    if not isinstance(capture, dict):
        raise SystemExit("ERROR: capture_model missing")
    for key in ("gatt_attempted", "rfcomm_attempted"):
        if capture.get(key) is not False:
            raise SystemExit(f"ERROR: {key} must be false")
    for key in ("application_payload_reads", "application_payload_writes"):
        if capture.get(key) != 0:
            raise SystemExit(f"ERROR: {key} must be zero")

    print("R1_3_3_2_25_2_1_PUBLICATION_VERIFY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
