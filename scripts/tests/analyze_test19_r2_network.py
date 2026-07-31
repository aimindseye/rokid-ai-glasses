#!/usr/bin/env python3
"""Classify PCAPdroid CSV traffic for Test 19 r2 without treating stock traffic as custom-app traffic."""
from __future__ import annotations

import argparse
import csv
import ipaddress
import json
from pathlib import Path

CUSTOM_PACKAGE = "org.aimindseye.rokid.cxrlqualification"
HI_ROKID_PACKAGE = "com.rokid.sprite.global.aiapp"
APP_KEYS = ("package", "package_name", "app_package", "app", "application", "uid_name", "app_name")
HOST_KEYS = ("remote_host", "dst_name", "host", "domain", "server_name", "sni")
IP_KEYS = ("remote_ip", "dst_ip", "destination_ip", "ip")
LOCAL_SUFFIXES = (".local", ".lan", ".home", ".internal")


def first(row: dict[str, str], keys: tuple[str, ...]) -> str:
    lowered = {str(key).strip().lower(): str(value).strip() for key, value in row.items()}
    return next((lowered[key] for key in keys if lowered.get(key)), "")


def local_destination(host: str, ip_value: str) -> bool:
    if ip_value:
        try:
            value = ipaddress.ip_address(ip_value.split("%")[0])
            if value.is_private or value.is_loopback or value.is_link_local or value.is_multicast or value.is_unspecified:
                return True
        except ValueError:
            pass
    normalized = host.lower()
    return normalized == "localhost" or normalized.endswith(LOCAL_SUFFIXES)


def app_scope(value: str) -> str:
    normalized = value.lower()
    if CUSTOM_PACKAGE in normalized or "test 19 r2" in normalized or "cxrlqualification" in normalized:
        return "custom"
    if HI_ROKID_PACKAGE in normalized or "hi rokid" in normalized or "global.aiapp" in normalized:
        return "hi_rokid"
    return "other" if normalized else "unknown"


def analyze(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = [str(item).strip().lower() for item in (reader.fieldnames or [])]

    app_column_present = any(key in fieldnames for key in APP_KEYS)
    counts = {
        "custom_local": 0,
        "custom_public": 0,
        "hi_rokid_local": 0,
        "hi_rokid_public": 0,
        "other": 0,
        "unknown": 0,
    }
    public_destinations: list[dict[str, str | int]] = []
    for line_number, row in enumerate(rows, 2):
        app_value = first(row, APP_KEYS)
        host = first(row, HOST_KEYS)
        ip_value = first(row, IP_KEYS)
        scope = app_scope(app_value)
        is_local = local_destination(host, ip_value)
        if scope == "custom":
            key = "custom_local" if is_local else "custom_public"
        elif scope == "hi_rokid":
            key = "hi_rokid_local" if is_local else "hi_rokid_public"
        elif scope == "other":
            key = "other"
        else:
            key = "unknown"
        counts[key] += 1
        if not is_local and (host or ip_value):
            public_destinations.append({
                "line": line_number,
                "scope": scope,
                "host": host,
                "ip": ip_value,
            })

    if not rows or not app_column_present:
        gate = "BLOCKED"
        exit_code = 30
        reason = "CSV_EMPTY_OR_APP_IDENTITY_COLUMN_MISSING"
    elif counts["custom_public"] > 0:
        gate = "FAIL"
        exit_code = 10
        reason = "CUSTOM_APP_PUBLIC_DESTINATION_OBSERVED"
    else:
        gate = "PASS"
        exit_code = 0
        reason = "NO_CUSTOM_APP_PUBLIC_DESTINATION_OBSERVED"

    return {
        "schema": "rokid.test19-r2.network-privacy.v1",
        "row_count": len(rows),
        "app_identity_column_present": app_column_present,
        "counts": counts,
        "public_destinations": public_destinations,
        "gate": gate,
        "reason": reason,
        "exit_code": exit_code,
        "interpretation": "Hi Rokid public traffic is reported separately and is not attributed to the custom app.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = analyze(Path(args.csv))
    except Exception as error:  # noqa: BLE001
        print("TEST19_R2_NETWORK_PRIVACY_GATE=BLOCKED")
        print(f"ERROR={error}")
        return 30
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TEST19_R2_NETWORK_PRIVACY_GATE={result['gate']}")
    print(f"TEST19_R2_CUSTOM_PUBLIC_DESTINATION_COUNT={result['counts']['custom_public']}")
    print(f"TEST19_R2_HI_ROKID_PUBLIC_DESTINATION_COUNT={result['counts']['hi_rokid_public']}")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
