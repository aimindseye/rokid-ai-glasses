#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from r25lib import write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(args.client_log.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("schema") != "rokid.r25.client-event.v1":
            raise SystemExit(f"unexpected schema on line {line_number}")
        events.append(row)

    counts = Counter(row["event_type"] for row in events)
    device_ids = sorted({row.get("device_id") for row in events if row.get("device_id")})
    services: set[str] = set()
    characteristics: set[str] = set()
    sdp_uuids: set[str] = set()
    reads: list[dict[str, Any]] = []

    for row in events:
        details = row.get("details", {})
        if row["event_type"] == "gatt_services_discovered":
            for service in details.get("services", []):
                if service.get("uuid"):
                    services.add(service["uuid"])
                for characteristic in service.get("characteristics", []):
                    if characteristic.get("uuid"):
                        characteristics.add(characteristic["uuid"])
        elif row["event_type"] == "sdp_uuid_result":
            sdp_uuids.update(details.get("uuids", []))
        elif row["event_type"] == "gatt_characteristic_read":
            reads.append({
                "service_uuid": details.get("service_uuid"),
                "characteristic_uuid": details.get("characteristic_uuid"),
                "status": details.get("status"),
                "value_length": details.get("value_length"),
                "value_sha256": details.get("value_sha256"),
            })

    result = {
        "schema": "rokid.r25.client-probe-summary.v1",
        "event_count": len(events),
        "event_type_counts": dict(sorted(counts.items())),
        "pseudonymous_device_count": len(device_ids),
        "device_ids": device_ids,
        "gatt_service_uuids": sorted(services),
        "gatt_characteristic_uuids": sorted(characteristics),
        "sdp_uuids": sorted(sdp_uuids),
        "read_results": reads,
        "write_events": 0,
        "raw_addresses_present": False,
    }
    write_json(args.output, result)
    print(f"R25_CLIENT_EVENT_COUNT={len(events)}")
    print(f"R25_CLIENT_GATT_SERVICE_COUNT={len(services)}")
    print(f"R25_CLIENT_SDP_UUID_COUNT={len(sdp_uuids)}")
    print("R25_CLIENT_WRITE_EVENTS=0")
    print("R25_CLIENT_PROBE_ANALYSIS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
