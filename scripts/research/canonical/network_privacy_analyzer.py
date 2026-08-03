#!/usr/bin/env python3
"""Profile-driven host-only Test 19 PCAPdroid CSV privacy analyzer."""
from __future__ import annotations

import csv
import ipaddress
import json
from pathlib import Path

try:
    from primitives import read_json
except ImportError:
    from scripts.research.canonical.primitives import read_json

PROFILE_PATH = Path(__file__).resolve().parent / "profiles/test19-network-analyzers.json"

HOST_KEYS = ("remote_host", "dst_name", "host", "domain", "server_name", "sni")
IP_KEYS = ("remote_ip", "dst_ip", "destination_ip", "ip")
LOCAL_SUFFIXES = (".local", ".lan", ".home", ".internal")
CUSTOM_PACKAGE = "org.aimindseye.rokid.cxrlqualification"
HI_ROKID_PACKAGE = "com.rokid.sprite.global.aiapp"
APP_KEYS = ("package", "package_name", "app_package", "app", "application", "uid_name", "app_name")


def _profiles() -> list[dict]:
    return read_json(PROFILE_PATH)["profiles"]


def _profile(revision: str) -> dict:
    for row in _profiles():
        if row["revision"] == revision:
            return row
    raise KeyError(f"unknown Test 19 network analyzer revision: {revision}")


def list_profiles() -> int:
    for row in _profiles():
        print(f"{row['revision']}\t{row['legacy_path']}\t{row['schema']}")
    return 0


def is_local_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.strip().split("%")[0])
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified
    except ValueError:
        return False


def first(row: dict[str, str], keys: tuple[str, ...]) -> str:
    lowered = {str(key).strip().lower(): str(value).strip() for key, value in row.items()}
    return next((lowered[key] for key in keys if lowered.get(key)), "")


def local_destination(host: str, ip_value: str) -> bool:
    if ip_value and is_local_ip(ip_value):
        return True
    normalized = host.lower()
    return normalized == "localhost" or normalized.endswith(LOCAL_SUFFIXES)


def app_scope(value: str) -> str:
    normalized = value.lower()
    if CUSTOM_PACKAGE in normalized or "test 19 r2" in normalized or "cxrlqualification" in normalized:
        return "custom"
    if HI_ROKID_PACKAGE in normalized or "hi rokid" in normalized or "global.aiapp" in normalized:
        return "hi_rokid"
    return "other" if normalized else "unknown"


def analyze_r1(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    public: list[dict] = []
    local: list[dict] = []
    unknown: list[dict] = []
    for line_number, row in enumerate(rows, 2):
        host = next((str(row.get(key, "")).strip() for key in HOST_KEYS if str(row.get(key, "")).strip()), "")
        ip_value = next((str(row.get(key, "")).strip() for key in IP_KEYS if str(row.get(key, "")).strip()), "")
        value = host or ip_value
        rec = {"line": line_number, "host": host, "ip": ip_value}
        if ip_value and is_local_ip(ip_value):
            local.append(rec)
        elif host and (host.lower() == "localhost" or host.lower().endswith(LOCAL_SUFFIXES)):
            local.append(rec)
        elif value:
            public.append(rec)
        else:
            unknown.append(rec)
    return {
        "schema": "rokid.test19-r1.network-privacy.v1",
        "row_count": len(rows),
        "local_destination_count": len(local),
        "public_destination_count": len(public),
        "unknown_destination_count": len(unknown),
        "public_destinations": public,
        "gate": "PASS" if rows and not public else "FAIL",
    }


def analyze_r2(path: Path) -> dict:
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


def analyze_revision(
    repo: Path,
    revision: str,
    csv_path: Path,
    output: Path,
    *,
    emit_output: bool = True,
) -> tuple[int, dict | None, list[str]]:
    profile = _profile(revision)
    mode = profile["mode"]
    lines: list[str] = []
    if mode == "r1_destination_gate":
        result = analyze_r1(csv_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        lines = [
            f"TEST19_R1_LOCAL_NETWORK_PRIVACY_GATE={result['gate']}",
            f"TEST19_R1_PUBLIC_DESTINATION_COUNT={result['public_destination_count']}",
        ]
        rc = 0 if result["gate"] == "PASS" else 4
    elif mode == "r2_app_scoped_gate":
        try:
            result = analyze_r2(csv_path)
        except Exception as error:  # historical r2 compatibility
            lines = ["TEST19_R2_NETWORK_PRIVACY_GATE=BLOCKED", f"ERROR={error}"]
            if emit_output:
                print("\n".join(lines))
            return 30, None, lines
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        lines = [
            f"TEST19_R2_NETWORK_PRIVACY_GATE={result['gate']}",
            f"TEST19_R2_CUSTOM_PUBLIC_DESTINATION_COUNT={result['counts']['custom_public']}",
            f"TEST19_R2_HI_ROKID_PUBLIC_DESTINATION_COUNT={result['counts']['hi_rokid_public']}",
        ]
        rc = int(result["exit_code"])
    else:
        raise ValueError(f"unsupported network analyzer mode: {mode}")
    if emit_output:
        print("\n".join(lines))
    return rc, result, lines
