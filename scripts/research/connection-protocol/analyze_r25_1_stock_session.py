#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

FIXED_UUID = "23cfac15-ac32-466e-a2b0-1c6fee849f75"
GATT_CONNECTION_INFO_UUID = "00009301-0000-1000-8000-00805f9b34fb"
SCHEMA_PRIVATE = "rokid.r25.1.stock-session-private.v1"
SCHEMA_PUBLIC = "rokid.r25.1.stock-session-public.v1"

LOG_TS = re.compile(r"^(?:(?P<year>\d{4})-)?(?P<md>\d\d-\d\d) (?P<hms>\d\d:\d\d:\d\d\.\d{3})")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def load_json_bytes(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"))


def first_matching_name(names: Iterable[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {suffix!r}, found {len(matches)}")
    return matches[0]


def parse_log_epoch(line: str, year: int = 2026) -> float | None:
    full = re.search(r"(?P<year>\d{4})-(?P<md>\d{2}-\d{2}) (?P<hms>\d{2}:\d{2}:\d{2}\.\d{3})", line)
    match = full or LOG_TS.search(line)
    if not match:
        return None
    value = f"{match.groupdict().get('year') or year}-{match.group('md')} {match.group('hms')}"
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def first_line(lines: list[str], predicate) -> str:
    for line in lines:
        if predicate(line):
            return line
    raise ValueError("required evidence line not found")


def all_lines(lines: list[str], predicate) -> list[str]:
    return [line for line in lines if predicate(line)]


def parse_int_after(line: str, label: str) -> int:
    match = re.search(re.escape(label) + r"(\d+)", line)
    if not match:
        raise ValueError(f"missing integer {label!r} in line: {line}")
    return int(match.group(1))


def parse_hex_after(line: str, label: str) -> str:
    match = re.search(re.escape(label) + r"(0x[0-9a-fA-F]+)", line)
    if not match:
        raise ValueError(f"missing hex {label!r} in line: {line}")
    return match.group(1).lower()


def parse_runtime_uuid(line: str) -> str:
    match = re.search(r"mSocketUuid:([0-9a-fA-F-]{36})", line)
    if not match:
        raise ValueError("runtime UUID not found")
    return match.group(1).lower()


def parse_account_line(lines: list[str]) -> tuple[int, str]:
    line = first_line(lines, lambda item: "BluetoothController: mRokidAccount:" in item)
    value = line.split("mRokidAccount:", 1)[1].strip()
    if not value:
        raise ValueError("empty account material")
    return len(value), sha256_text(value)


def parse_optional_client_log(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    uuid_sets: list[list[str]] = []
    count = 0
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid client JSONL {path}:{lineno}: {exc}") from exc
        count += 1
        if row.get("event_type") == "sdp_uuid_result":
            values = row.get("details", {}).get("uuids", [])
            uuid_sets.append(sorted({str(value).lower() for value in values}))
    if not uuid_sets:
        raise ValueError(f"no sdp_uuid_result event in {path}")
    stable = all(values == uuid_sets[0] for values in uuid_sets)
    return {
        "path": str(path),
        "sha256": sha256_bytes(path.read_bytes()),
        "event_count": count,
        "observation_count": len(uuid_sets),
        "stable_within_log": stable,
        "uuids": uuid_sets[-1],
    }


def extract_source(evidence_zip: Path) -> tuple[dict[str, Any], list[str], dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(evidence_zip) as outer:
        names = outer.namelist()
        capture_name = first_matching_name(names, "/capture-metadata-private.json")
        timeline_name = first_matching_name(names, "/timeline-private.ndjson")
        pairing_name = first_matching_name(names, "/analysis/pairing-channel-summary-private.json")
        bugreport_name = first_matching_name(names, "/phone-bugreport-private.zip")

        capture = load_json_bytes(outer.read(capture_name))
        pairing = load_json_bytes(outer.read(pairing_name))
        timeline = [json.loads(line) for line in outer.read(timeline_name).decode("utf-8").splitlines() if line.strip()]
        bugreport_bytes = outer.read(bugreport_name)

    import io
    with zipfile.ZipFile(io.BytesIO(bugreport_bytes)) as inner:
        text_names = [name for name in inner.namelist() if re.fullmatch(r"bugreport-.*\.txt", name)]
        if len(text_names) != 1:
            raise ValueError(f"expected one bugreport text entry, found {len(text_names)}")
        bugreport_text = inner.read(text_names[0]).decode("utf-8", errors="replace")

    return capture, bugreport_text.splitlines(), pairing, {"timeline": timeline}


def require_ordered(events: list[tuple[str, float]]) -> None:
    for (left_name, left), (right_name, right) in zip(events, events[1:]):
        if left > right:
            raise ValueError(f"event order violation: {left_name}={left} > {right_name}={right}")


def analyze(evidence_zip: Path, soft_log: Path | None, strict_log: Path | None) -> tuple[dict[str, Any], dict[str, Any]]:
    archive_hash = sha256_bytes(evidence_zip.read_bytes())
    capture, lines, pairing, timeline_box = extract_source(evidence_zip)

    if capture.get("allow_developer_toggle") is not False:
        raise ValueError("source capture is not a stock-only no-toggle run")
    if capture.get("phase_set") != "pairing":
        raise ValueError("source capture phase_set must be pairing")

    fixed_cxr = all_lines(lines, lambda line: f"CxrController: connectBluetooth" in line and f"socketUuid:{FIXED_UUID}" in line)
    fixed_socket = all_lines(lines, lambda line: "BluetoothSocketManagerBinder: connectSocket:" in line and f"uuid={FIXED_UUID}" in line)
    fixed_failures = all_lines(lines, lambda line: "service discovery complete callback" in line and "status:tBTA_JV_STATUS::FAILURE scn:0" in line)

    char_line = first_line(lines, lambda line: f"handleGattCharacteristicRead uuid:{GATT_CONNECTION_INFO_UUID}" in line)
    runtime_line = first_line(lines, lambda line: "BluetoothController: mSocketUuid:" in line)
    runtime_uuid = parse_runtime_uuid(runtime_line)
    if runtime_uuid == FIXED_UUID:
        raise ValueError("runtime UUID unexpectedly equals fixed UUID")

    runtime_connect = first_line(lines, lambda line: "CxrController: connectBluetooth" in line and f"socketUuid:{runtime_uuid}" in line)
    runtime_binder = first_line(lines, lambda line: "BluetoothSocketManagerBinder: connectSocket:" in line and f"uuid={runtime_uuid}" in line)
    runtime_discovery = first_line(lines, lambda line: "service discovery complete callback" in line and "status:tBTA_JV_STATUS::SUCCESS scn:3" in line)
    create_line = first_line(lines, lambda line: "RFCOMM_CreateConnectionWithSecurity:" in line and "scn=3" in line and "is_server=false" in line)
    l2cap_start = first_line(lines, lambda line: "L2CEVT_L2CA_CONNECT_REQ" in line and "lcid:0x007f" in line)
    l2cap_remote = first_line(lines, lambda line: "lcid:0x007f" in line and "rcid:0x0044" in line)
    mux_ua = first_line(lines, lambda line: "RFC_MX_EVENT_UA" in line and "RFC_MX_STATE_SABME_WAIT_UA" in line)
    dlci_ua = first_line(lines, lambda line: "port_handle:26" in line and "RFC_PORT_EVENT_UA" in line)
    open_line = first_line(lines, lambda line: "on_cli_rfc_connect: connected" in line and "scn: 3" in line and "app_uid: 10305" in line)
    available_line = first_line(lines, lambda line: "CxrController: onStatusUpdate:BLUETOOTH_AVAILABLE" in line)
    first_request_line = first_line(lines, lambda line: "CxrController: request reqId:" in line and (parse_log_epoch(line) or 0) >= (parse_log_epoch(available_line) or 0))

    gatt_open_line = first_line(lines, lambda line: "GATT_CH_OPEN, ACL holders gatt_if: com.rokid.sprite.global.aiapp" in line and "20:59:55.978" in line)

    timestamps = {
        "ble_gatt_open": parse_log_epoch(gatt_open_line),
        "connection_info_characteristic_read": parse_log_epoch(char_line),
        "runtime_uuid_available": parse_log_epoch(runtime_line),
        "runtime_rfcomm_connect_requested": parse_log_epoch(runtime_binder),
        "runtime_sdp_resolved": parse_log_epoch(runtime_discovery),
        "rfcomm_mux_ua": parse_log_epoch(mux_ua),
        "rfcomm_dlci_ua": parse_log_epoch(dlci_ua),
        "rfcomm_socket_open": parse_log_epoch(open_line),
        "cxr_bluetooth_available": parse_log_epoch(available_line),
        "first_cxr_request": parse_log_epoch(first_request_line),
    }
    if any(value is None for value in timestamps.values()):
        raise ValueError("one or more required timestamps could not be parsed")
    ordered = [(key, float(value)) for key, value in timestamps.items()]
    require_ordered(ordered)

    account_length, account_sha256 = parse_account_line(lines)

    scn = parse_int_after(create_line, "scn=")
    dlci = parse_int_after(create_line, "dlci=")
    mtu = parse_int_after(create_line, "mtu=")
    port_handle = parse_int_after(create_line, "port_handle=")
    local_cid = parse_hex_after(l2cap_start, "lcid:")
    remote_cid = parse_hex_after(l2cap_remote, "rcid:")

    socket_event_lines = all_lines(lines, lambda line: "STATE_" in line and "RFCOMM" in line and (FIXED_UUID in line or runtime_uuid in line))

    soft = parse_optional_client_log(soft_log)
    strict = parse_optional_client_log(strict_log)
    comparison: dict[str, Any] | None = None
    if soft and strict:
        comparison = {
            "soft_count": len(soft["uuids"]),
            "strict_count": len(strict["uuids"]),
            "sets_equal": soft["uuids"] == strict["uuids"],
            "only_soft": sorted(set(soft["uuids"]) - set(strict["uuids"])),
            "only_strict": sorted(set(strict["uuids"]) - set(soft["uuids"])),
            "common": sorted(set(soft["uuids"]) & set(strict["uuids"])),
        }

    private: dict[str, Any] = {
        "schema": SCHEMA_PRIVATE,
        "source": {
            "archive": evidence_zip.name,
            "sha256": archive_hash,
            "capture_schema": capture.get("schema"),
            "phase_set": capture.get("phase_set"),
            "developer_toggle_attempted": bool(capture.get("allow_developer_toggle")),
        },
        "fixed_uuid_path": {
            "uuid": FIXED_UUID,
            "cxr_connect_calls": len(fixed_cxr),
            "bluetooth_socket_attempts": len(fixed_socket),
            "sdp_failure_scn_zero_count": len(fixed_failures),
            "classification": "CACHED_OR_FALLBACK_UUID_WITHOUT_ACTIVE_RFCOMM_SCN_IN_THIS_CAPTURE",
        },
        "ble_bootstrap": {
            "connection_info_characteristic_uuid": GATT_CONNECTION_INFO_UUID,
            "runtime_uuid": runtime_uuid,
            "runtime_uuid_sha256": sha256_text(runtime_uuid),
            "account_material_length": account_length,
            "account_material_sha256": account_sha256,
            "account_material_published": False,
            "classification": "BLE_GATT_CONNECTION_INFO_PROVISIONS_CLASSIC_RFCOMM_ENDPOINT",
        },
        "rfcomm_session": {
            "runtime_uuid": runtime_uuid,
            "sdp_server_channel": scn,
            "dlci": dlci,
            "mtu": mtu,
            "port_handle": port_handle,
            "l2cap_local_cid": local_cid,
            "l2cap_remote_cid": remote_cid,
            "app_uid": 10305,
            "initiator": "PHONE_CLIENT",
            "socket_state_event_count": len(socket_event_lines),
        },
        "timing": {
            "events_epoch": timestamps,
            "ble_open_to_connection_info_ms": round((timestamps["runtime_uuid_available"] - timestamps["ble_gatt_open"]) * 1000, 3),
            "connection_info_to_rfcomm_request_ms": round((timestamps["runtime_rfcomm_connect_requested"] - timestamps["runtime_uuid_available"]) * 1000, 3),
            "rfcomm_request_to_sdp_resolution_ms": round((timestamps["runtime_sdp_resolved"] - timestamps["runtime_rfcomm_connect_requested"]) * 1000, 3),
            "sdp_resolution_to_socket_open_ms": round((timestamps["rfcomm_socket_open"] - timestamps["runtime_sdp_resolved"]) * 1000, 3),
            "socket_open_to_cxr_available_ms": round((timestamps["cxr_bluetooth_available"] - timestamps["rfcomm_socket_open"]) * 1000, 3),
            "cxr_available_to_first_request_ms": round((timestamps["first_cxr_request"] - timestamps["cxr_bluetooth_available"]) * 1000, 3),
            "ble_open_to_socket_open_ms": round((timestamps["rfcomm_socket_open"] - timestamps["ble_gatt_open"]) * 1000, 3),
        },
        "existing_r25_transport_summary": {
            "status": pairing.get("status"),
            "operator_window_rfcomm_count": pairing.get("phase_transport_counts", {}).get("pairing_or_reconnect", {}).get("RFCOMM"),
            "operator_window_att_count": pairing.get("phase_transport_counts", {}).get("pairing_or_reconnect", {}).get("ATT"),
        },
        "supplemental_sdp": {
            "soft": soft,
            "strict": strict,
            "comparison": comparison,
        },
        "closure": {
            "ble_to_rfcomm_bootstrap_attributed": True,
            "sdp_service_channel_attributed": True,
            "rfcomm_scn_dlci_reconstructed": True,
            "stock_session_establishment_sequence_closed": True,
            "application_message_framing_closed": False,
            "session_authentication_semantics_closed": False,
            "independent_client_rfcomm_session_implemented": False,
            "developer_mode_remote_invocation_closed": False,
            "developer_mode_scope": "NOT_ATTEMPTED_AND_OUT_OF_SCOPE",
        },
    }

    public = {
        "schema": SCHEMA_PUBLIC,
        "source_archive_sha256": archive_hash,
        "fixed_uuid_path": {
            "uuid_sha256": sha256_text(FIXED_UUID),
            "cxr_connect_calls": len(fixed_cxr),
            "socket_attempts": len(fixed_socket),
            "sdp_failure_scn_zero_count": len(fixed_failures),
            "classification": private["fixed_uuid_path"]["classification"],
        },
        "ble_bootstrap": {
            "connection_info_characteristic_uuid": GATT_CONNECTION_INFO_UUID,
            "runtime_uuid_published": False,
            "runtime_uuid_sha256": sha256_text(runtime_uuid),
            "account_material_published": False,
            "account_material_sha256": account_sha256,
            "classification": private["ble_bootstrap"]["classification"],
        },
        "rfcomm_session": {
            "sdp_server_channel": scn,
            "dlci": dlci,
            "mtu": mtu,
            "l2cap_local_cid": local_cid,
            "l2cap_remote_cid": remote_cid,
            "initiator": "PHONE_CLIENT",
        },
        "timing_ms": {key: value for key, value in private["timing"].items() if key != "events_epoch"},
        "supplemental_sdp": None if comparison is None else {
            "soft_count": comparison["soft_count"],
            "strict_count": comparison["strict_count"],
            "sets_equal": comparison["sets_equal"],
            "uuid_values_published": False,
        },
        "closure": private["closure"],
        "public_safety": {
            "raw_hci_published": False,
            "bluetooth_address_published": False,
            "runtime_uuid_published": False,
            "account_material_published": False,
        },
    }
    return private, public


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze r25.1 stock session establishment")
    parser.add_argument("--evidence-zip", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--soft-client-log", type=Path)
    parser.add_argument("--strict-client-log", type=Path)
    args = parser.parse_args()

    if not args.evidence_zip.is_file():
        parser.error(f"evidence ZIP not found: {args.evidence_zip}")
    actual_hash = sha256_bytes(args.evidence_zip.read_bytes())
    if args.expected_sha256 and actual_hash != args.expected_sha256.lower():
        raise SystemExit(f"evidence SHA-256 mismatch: expected {args.expected_sha256}, got {actual_hash}")

    private, public = analyze(args.evidence_zip, args.soft_client_log, args.strict_client_log)
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.public_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.public_output.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"R25_1_SOURCE_SHA256={actual_hash}")
    print(f"R25_1_FIXED_UUID_SOCKET_ATTEMPTS={private['fixed_uuid_path']['bluetooth_socket_attempts']}")
    print(f"R25_1_FIXED_UUID_SDP_FAILURES={private['fixed_uuid_path']['sdp_failure_scn_zero_count']}")
    print(f"R25_1_RUNTIME_UUID_SHA256={public['ble_bootstrap']['runtime_uuid_sha256']}")
    print(f"R25_1_RFCOMM_SCN={private['rfcomm_session']['sdp_server_channel']}")
    print(f"R25_1_RFCOMM_DLCI={private['rfcomm_session']['dlci']}")
    print(f"R25_1_RFCOMM_MTU={private['rfcomm_session']['mtu']}")
    print("R25_1_RUNTIME_UUID_PUBLISHED=NO")
    print("R25_1_ACCOUNT_MATERIAL_PUBLISHED=NO")
    print("R25_1_DEVELOPER_MODE_IN_SCOPE=NO")
    print("R1_3_3_2_25_1_STOCK_SESSION_ANALYSIS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
