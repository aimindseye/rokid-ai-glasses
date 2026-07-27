#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

MAC = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")
UUID = re.compile(r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication", type=Path, required=True)
    args = parser.parse_args()
    raw = args.publication.read_text(encoding="utf-8")
    value = json.loads(raw)
    endpoint = value.get("endpoint", {})
    boundary = value.get("connection_boundary", {})

    failures = []
    if MAC.search(raw):
        failures.append("raw MAC-shaped value present")
    if UUID.search(raw):
        failures.append("raw UUID-shaped value present")
    if endpoint.get("address_published") is not False:
        failures.append("address publication flag")
    if endpoint.get("runtime_uuid_published") is not False:
        failures.append("runtime UUID publication flag")
    if boundary.get("application_payload_reads") != 0:
        failures.append("payload read count")
    if boundary.get("application_payload_writes") != 0:
        failures.append("payload write count")
    if boundary.get("application_data_streams_obtained") is not False:
        failures.append("application streams flag")
    if boundary.get("independent_gatt_attempted") is not False:
        failures.append("GATT boundary")
    if failures:
        raise SystemExit("ERROR: sanitized publication gate failed: " + ", ".join(failures))

    print("R25_2_2_2_PUBLICATION_RAW_ADDRESS_PRESENT=NO")
    print("R25_2_2_2_PUBLICATION_RAW_RUNTIME_UUID_PRESENT=NO")
    print("R25_2_2_2_PUBLICATION_ZERO_PAYLOAD=YES")
    print("R25_2_2_2_PUBLICATION_VERIFY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
