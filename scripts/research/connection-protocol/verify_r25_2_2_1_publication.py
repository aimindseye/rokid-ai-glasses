#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

MAC_RE = re.compile(
    r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])"
)
UUID_RE = re.compile(
    r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}(?![0-9A-Fa-f])"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", type=Path, required=True)
    args = parser.parse_args()
    raw = args.publication.read_text(encoding="utf-8")
    value = json.loads(raw)

    failures: list[str] = []
    if value.get("runtime_address_published") is not False:
        failures.append("runtime address publication flag is not false")
    if value.get("runtime_uuid_published") is not False:
        failures.append("runtime UUID publication flag is not false")
    if MAC_RE.search(raw):
        failures.append("raw Bluetooth address found in publication")
    if UUID_RE.search(raw):
        failures.append("raw 128-bit UUID found in publication")

    boundary = value.get("connection_boundary", {})
    expected = {
        "offline_reanalysis_only": True,
        "independent_gatt_attempted": False,
        "independent_rfcomm_attempted": False,
        "automatic_connection_performed": False,
        "application_payload_reads": 0,
        "application_payload_writes": 0,
        "developer_mode_action_performed": False,
    }
    for key, wanted in expected.items():
        if boundary.get(key) != wanted:
            failures.append(f"connection boundary mismatch: {key}")

    if failures:
        print("R25_2_2_1_PUBLICATION_VERIFY=FAIL")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("R25_2_2_1_RUNTIME_ADDRESS_PUBLICATION=NO")
    print("R25_2_2_1_RUNTIME_UUID_PUBLICATION=NO")
    print("R25_2_2_1_PUBLICATION_VERIFY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
