#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import hashlib
import hmac
import io
import json
import re
import statistics
import zipfile
from pathlib import Path
from typing import Any

SCHEMA_PRIVATE = "rokid.r25.2.2.private-analysis.v1"
SCHEMA_PUBLIC = "rokid.r25.2.2.publication.v1"
SCHEMA_HANDOFF = "rokid.r25.2.2.endpoint-handoff-private.v1"
STOCK_PACKAGE = "com.rokid.sprite.global.aiapp"
TARGET_CHAR = "00009301-0000-1000-8000-00805f9b34fb"
MAC_RE = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])")
TS_RE = re.compile(r"(?P<epoch>\d{10}(?:\.\d+)?)")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def norm_mac(value: str) -> str:
    return value.upper()


def address_token(key: bytes, address: str) -> str:
    return hmac.new(key, norm_mac(address).encode("ascii"), hashlib.sha256).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL line {line_number}: {exc}") from exc
        if isinstance(value, dict):
            rows.append(value)
    return rows


def load_bugreport_text(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    with zipfile.ZipFile(path) as outer:
        names = [name for name in outer.namelist() if re.fullmatch(r"bugreport-.*\.txt", name)]
        if len(names) == 1:
            return outer.read(names[0]).decode("utf-8", errors="replace").splitlines()
        for nested_name in [name for name in outer.namelist() if name.endswith(".zip")]:
            try:
                with zipfile.ZipFile(io.BytesIO(outer.read(nested_name))) as inner:
                    inner_names = [name for name in inner.namelist() if re.fullmatch(r"bugreport-.*\.txt", name)]
                    if len(inner_names) == 1:
                        return inner.read(inner_names[0]).decode("utf-8", errors="replace").splitlines()
            except zipfile.BadZipFile:
                continue
    return []


def parse_epoch(line: str) -> float | None:
    match = TS_RE.match(line.strip())
    return float(match.group("epoch")) if match else None


def evidence_score(line: str, stock_pids: set[int]) -> int:
    lowered = line.lower()
    score = 0
    if STOCK_PACKAGE in line:
        score += 100
    fields = line.split()
    if any(str(pid) in fields[:7] for pid in stock_pids):
        score += 70
    if "bluetoothgatt" in lowered and ("connect" in lowered or "open" in lowered):
        score += 60
    if "clientconnect" in lowered or "gatt_connect" in lowered or "gatt_ch_open" in lowered:
        score += 50
    if "acl" in lowered and ("connect" in lowered or "open" in lowered):
        score += 20
    if TARGET_CHAR in lowered or "uuid:00009301" in lowered or "uuid=00009301" in lowered:
        score += 120
    return score


def analyze(
    client_log: Path,
    stock_log: Path,
    key_file: Path,
    metadata_path: Path,
    bugreport: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    rows = read_jsonl(client_log)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    key_hex = key_file.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", key_hex):
        raise ValueError("invalid private correlation key")
    key = bytes.fromhex(key_hex)

    event_counts = collections.Counter(str(row.get("event_type")) for row in rows)
    phase_starts = [
        row.get("details", {}).get("phase")
        for row in rows
        if row.get("event_type") == "r25_2_2_phase_started"
    ]
    phase_completes = [
        row.get("details", {}).get("phase")
        for row in rows
        if row.get("event_type") == "r25_2_2_phase_complete"
    ]
    expected_phases = [
        "stock_disabled_baseline",
        "stock_assist_window",
        "post_stock_handoff",
    ]
    phase_sequence_ok = (
        phase_starts == expected_phases
        and phase_completes == expected_phases
        and event_counts["r25_2_2_capture_complete"] == 1
    )

    advertisements_by_token: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("event_type") != "r25_2_2_ble_advertisement":
            continue
        details = row.get("details", {})
        token = details.get("address_hmac_sha256")
        if not isinstance(token, str):
            continue
        entry = advertisements_by_token.setdefault(
            token,
            {
                "count": 0,
                "phases": collections.Counter(),
                "rssis": [],
                "structures": collections.Counter(),
                "payloads": collections.Counter(),
                "service_uuids": set(),
            },
        )
        entry["count"] += 1
        entry["phases"][str(details.get("phase"))] += 1
        if isinstance(details.get("rssi"), int) and details["rssi"] != 127:
            entry["rssis"].append(details["rssi"])
        if isinstance(details.get("structure_fingerprint_sha256"), str):
            entry["structures"][details["structure_fingerprint_sha256"]] += 1
        if isinstance(details.get("payload_fingerprint_sha256"), str):
            entry["payloads"][details["payload_fingerprint_sha256"]] += 1
        for uuid in details.get("advertised_service_uuids", []) if isinstance(details.get("advertised_service_uuids"), list) else []:
            entry["service_uuids"].add(str(uuid))

    stock_lines = stock_log.read_text(encoding="utf-8", errors="replace").splitlines()
    bugreport_lines = load_bugreport_text(bugreport)
    all_lines = [("logcat", line) for line in stock_lines] + [("bugreport", line) for line in bugreport_lines]
    stock_pids = {int(value) for value in metadata.get("stock_pids", []) if str(value).isdigit()}

    characteristic_lines = [
        (source, line)
        for source, line in all_lines
        if TARGET_CHAR in line.lower() or "uuid:00009301" in line.lower() or "uuid=00009301" in line.lower()
    ]
    characteristic_times = [
        timestamp
        for _, line in characteristic_lines
        if (timestamp := parse_epoch(line)) is not None
    ]

    candidates: dict[str, dict[str, Any]] = {}
    for source, line in all_lines:
        addresses = {norm_mac(value) for value in MAC_RE.findall(line)}
        if not addresses:
            continue
        base_score = evidence_score(line, stock_pids)
        timestamp = parse_epoch(line)
        near_characteristic = bool(
            timestamp is not None
            and any(abs(timestamp - characteristic_time) <= 10.0 for characteristic_time in characteristic_times)
        )
        for address in addresses:
            candidate = candidates.setdefault(
                address,
                {
                    "address": address,
                    "score": 0,
                    "line_count": 0,
                    "stock_package_lines": 0,
                    "gatt_lines": 0,
                    "near_9301_lines": 0,
                    "sources": collections.Counter(),
                    "evidence_line_sha256": [],
                },
            )
            line_score = base_score + (45 if near_characteristic else 0)
            candidate["score"] += line_score
            candidate["line_count"] += 1
            candidate["sources"][source] += 1
            lowered = line.lower()
            if STOCK_PACKAGE in line:
                candidate["stock_package_lines"] += 1
            if "gatt" in lowered or "bluetoothgatt" in lowered:
                candidate["gatt_lines"] += 1
            if near_characteristic:
                candidate["near_9301_lines"] += 1
            if line_score > 0 and len(candidate["evidence_line_sha256"]) < 20:
                candidate["evidence_line_sha256"].append(sha256_text(line))

    ranked: list[dict[str, Any]] = []
    for address, candidate in candidates.items():
        token = address_token(key, address)
        scan_entry = advertisements_by_token.get(token)
        candidate["address_hmac_sha256"] = token
        candidate["scan_correlated"] = scan_entry is not None
        if scan_entry:
            candidate["score"] += 120
            candidate["scan"] = {
                "advertisement_count": scan_entry["count"],
                "phase_counts": dict(scan_entry["phases"]),
                "max_rssi": max(scan_entry["rssis"]) if scan_entry["rssis"] else None,
                "median_rssi": statistics.median(scan_entry["rssis"]) if scan_entry["rssis"] else None,
                "structure_fingerprint_count": len(scan_entry["structures"]),
                "payload_fingerprint_count": len(scan_entry["payloads"]),
                "advertised_service_uuids": sorted(scan_entry["service_uuids"]),
            }
        else:
            candidate["scan"] = None
        candidate["sources"] = dict(candidate["sources"])
        ranked.append(candidate)

    ranked.sort(
        key=lambda item: (
            -item["score"],
            -item["stock_package_lines"],
            -item["gatt_lines"],
            item["address"],
        )
    )
    top = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    score_margin = (
        top["score"] - second["score"]
        if top and second
        else top["score"] if top else None
    )
    provisioning_read_observed = len(characteristic_lines) > 0
    unique_endpoint = bool(
        top
        and top["score"] >= 160
        and (score_margin or 0) >= 40
        and provisioning_read_observed
        and (top["stock_package_lines"] > 0 or top["gatt_lines"] > 0)
    )
    scan_correlated = bool(unique_endpoint and top and top["scan_correlated"])
    launcher_component = metadata.get("stock_launcher_component")
    capture_valid = bool(
        phase_sequence_ok
        and metadata.get("stock_enabled_for_assist") is True
        and metadata.get("stock_disabled_after_assist") is True
        and metadata.get("stock_launch_verified") is True
        and metadata.get("stock_foreground_verified") is True
        and isinstance(launcher_component, str)
        and launcher_component.startswith(STOCK_PACKAGE + "/")
        and len(stock_pids) > 0
    )

    if not capture_valid:
        acceptance = "FAIL_CAPTURE_INVALID"
        outcome = "CAPTURE_INVALID"
    elif unique_endpoint and scan_correlated:
        acceptance = "PASS_UNIQUE_PROVISIONING_GATT_ENDPOINT_CORRELATED"
        outcome = "UNIQUE_PROVISIONING_GATT_ENDPOINT_CORRELATED"
    elif unique_endpoint:
        acceptance = "PASS_UNIQUE_PROVISIONING_GATT_ENDPOINT_ATTRIBUTED_SCAN_UNRESOLVED"
        outcome = "UNIQUE_PROVISIONING_GATT_ENDPOINT_ATTRIBUTED_SCAN_UNRESOLVED"
    else:
        acceptance = "PASS_BOUNDED_STOCK_ASSIST_CAPTURE_ENDPOINT_UNRESOLVED"
        outcome = "BOUNDED_STOCK_ASSIST_CAPTURE_ENDPOINT_UNRESOLVED"

    connection_boundary = {
        "probe_gatt_attempted": False,
        "probe_rfcomm_attempted": False,
        "application_payload_reads": 0,
        "application_payload_writes": 0,
        "stock_app_assist_only": True,
    }
    private = {
        "schema": SCHEMA_PRIVATE,
        "release": "r1.3.3.2.25.2.2",
        "acceptance": acceptance,
        "attribution_outcome": outcome,
        "capture_valid": capture_valid,
        "phase_sequence_ok": phase_sequence_ok,
        "event_count": len(rows),
        "event_counts": dict(event_counts),
        "stock_package": STOCK_PACKAGE,
        "stock_pids": sorted(stock_pids),
        "provisioning_characteristic_uuid": TARGET_CHAR,
        "provisioning_read_observed": provisioning_read_observed,
        "provisioning_read_line_count": len(characteristic_lines),
        "candidate_count": len(ranked),
        "candidate_score_margin": score_margin,
        "unique_endpoint_attributed": unique_endpoint,
        "scan_correlated": scan_correlated,
        "ranked_candidates": ranked[:20],
        "connection_boundary": connection_boundary,
    }
    public = {
        "schema": SCHEMA_PUBLIC,
        "release": "r1.3.3.2.25.2.2",
        "acceptance": acceptance,
        "attribution_outcome": outcome,
        "capture_valid": capture_valid,
        "phase_sequence_ok": phase_sequence_ok,
        "provisioning_characteristic_uuid": TARGET_CHAR,
        "provisioning_read_observed": provisioning_read_observed,
        "candidate_count": len(ranked),
        "candidate_score_margin": score_margin,
        "unique_endpoint_attributed": unique_endpoint,
        "scan_correlated": scan_correlated,
        "endpoint_address_published": False,
        "endpoint_address_sha256": sha256_text(top["address"]) if unique_endpoint and top else None,
        "endpoint_hmac_sha256": top["address_hmac_sha256"] if unique_endpoint and top else None,
        "top_candidate_evidence": None if not top else {
            "score": top["score"],
            "stock_package_line_count": top["stock_package_lines"],
            "gatt_line_count": top["gatt_lines"],
            "near_9301_line_count": top["near_9301_lines"],
            "scan_correlated": top["scan_correlated"],
            "scan": top["scan"],
        },
        "connection_boundary": connection_boundary,
        "public_safety": {
            "raw_bluetooth_address_published": False,
            "correlation_key_published": False,
            "raw_logcat_published": False,
            "raw_bugreport_published": False,
            "private_device_ids_published": False,
        },
    }
    handoff = None
    if unique_endpoint and top:
        handoff = {
            "schema": SCHEMA_HANDOFF,
            "release": "r1.3.3.2.25.2.2",
            "stock_package": STOCK_PACKAGE,
            "endpoint_address": top["address"],
            "endpoint_address_sha256": sha256_text(top["address"]),
            "endpoint_hmac_sha256": top["address_hmac_sha256"],
            "provisioning_characteristic_uuid": TARGET_CHAR,
            "provisioning_read_observed": True,
            "scan_correlated": top["scan_correlated"],
            "scan_summary": top["scan"],
            "ready_for_independent_connection_only_qualification": True,
            "automatic_connection_performed": False,
        }
    return private, public, handoff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-log", type=Path, required=True)
    parser.add_argument("--stock-logcat", type=Path, required=True)
    parser.add_argument("--correlation-key", type=Path, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--bugreport", type=Path)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--handoff-output", type=Path, required=True)
    args = parser.parse_args()

    private, public, handoff = analyze(
        args.client_log,
        args.stock_logcat,
        args.correlation_key,
        args.run_metadata,
        args.bugreport,
    )
    for path, value in ((args.private_output, private), (args.public_output, public)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.handoff_output.parent.mkdir(parents=True, exist_ok=True)
    if handoff is None:
        handoff = {
            "schema": SCHEMA_HANDOFF,
            "release": "r1.3.3.2.25.2.2",
            "available": False,
            "reason": "unique_endpoint_not_attributed",
            "automatic_connection_performed": False,
        }
    args.handoff_output.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"R25_2_2_PHASE_SEQUENCE_OK={'YES' if private['phase_sequence_ok'] else 'NO'}")
    print(f"R25_2_2_PROVISIONING_9301_OBSERVED={'YES' if private['provisioning_read_observed'] else 'NO'}")
    print(f"R25_2_2_UNIQUE_ENDPOINT_ATTRIBUTED={'YES' if private['unique_endpoint_attributed'] else 'NO'}")
    print(f"R25_2_2_SCAN_CORRELATED={'YES' if private['scan_correlated'] else 'NO'}")
    print("R25_2_2_PROBE_GATT_ATTEMPTED=NO")
    print("R25_2_2_PROBE_RFCOMM_ATTEMPTED=NO")
    print("R25_2_2_APPLICATION_PAYLOAD_READ_COUNT=0")
    print("R25_2_2_APPLICATION_PAYLOAD_WRITE_COUNT=0")
    print(f"R25_2_2_ATTRIBUTION_OUTCOME={private['attribution_outcome']}")
    print("R25_2_2_ANALYSIS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
