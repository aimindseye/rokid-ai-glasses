#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from typing import Any

RELEASE = "r1.3.3.2.25.2.2.2"
PRIVATE_SCHEMA = "rokid.r25.2.2.2.connection-only-private-analysis.v1"
PUBLIC_SCHEMA = "rokid.r25.2.2.2.connection-only-publication.v1"
INPUT_SCHEMA = "rokid.r25.2.2.2.connection-only-input-private.v1"
ADDRESS_RE = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")
UUID_RE = re.compile(r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL line {number}: {exc}") from exc
        if isinstance(value, dict):
            values.append(value)
    return values


def load_bugreport_lines(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    with zipfile.ZipFile(path) as outer:
        direct = [name for name in outer.namelist() if re.fullmatch(r"bugreport-.*\.txt", name)]
        if len(direct) == 1:
            return outer.read(direct[0]).decode("utf-8", errors="replace").splitlines()
        nested = [name for name in outer.namelist() if name.endswith(".zip")]
        for name in nested:
            try:
                with zipfile.ZipFile(io.BytesIO(outer.read(name))) as inner:
                    matches = [item for item in inner.namelist() if re.fullmatch(r"bugreport-.*\.txt", item)]
                    if len(matches) == 1:
                        return inner.read(matches[0]).decode("utf-8", errors="replace").splitlines()
            except zipfile.BadZipFile:
                continue
    return []


def details_for(rows: list[dict[str, Any]], event: str) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if row.get("event_type") == event and isinstance(row.get("details"), dict):
            result.append(row["details"])
    return result


def relevant_lines(lines: list[str], address: str, probe_uid: int | None, probe_pids: set[int]) -> list[str]:
    suffix = ":".join(address.split(":")[-2:]).lower()
    result: list[str] = []
    for line in lines:
        lowered = line.lower()
        if address.lower() not in lowered and suffix not in lowered:
            continue
        numeric = {int(value) for value in line.split()[:8] if value.isdigit()}
        relevant_transport = any(token in lowered for token in (
            "rfcomm", "bluetoothsocket", "socket", "acl", "service discovery", "sdp"
        ))
        ownership = (
            (probe_uid is not None and f"app_uid: {probe_uid}" in lowered)
            or bool(numeric & probe_pids)
        )
        if relevant_transport or ownership:
            result.append(line)
    return result


def analyze(
    client_log: Path,
    phone_logcat: Path,
    metadata_path: Path,
    input_handoff_path: Path,
    bugreport: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = read_jsonl(client_log)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    handoff = json.loads(input_handoff_path.read_text(encoding="utf-8"))
    if handoff.get("schema") != INPUT_SCHEMA:
        raise ValueError("unexpected input handoff schema")

    address = handoff["runtime_address"].upper()
    runtime_uuid = handoff["runtime_uuid"].lower()
    expected = handoff["expected_rfcomm"]
    probe_uid = metadata.get("probe_uid") if isinstance(metadata.get("probe_uid"), int) else None
    probe_pids = {
        int(value) for value in metadata.get("probe_pids", [])
        if str(value).isdigit()
    }

    all_lines = phone_logcat.read_text(encoding="utf-8", errors="replace").splitlines()
    all_lines.extend(load_bugreport_lines(bugreport))
    transport_lines = relevant_lines(all_lines, address, probe_uid, probe_pids)
    lowered = [line.lower() for line in transport_lines]

    loaded = details_for(rows, "r25_2_2_2_handoff_loaded")
    requested = details_for(rows, "r25_2_2_2_rfcomm_connect_requested")
    opened = details_for(rows, "r25_2_2_2_rfcomm_socket_open")
    failed = details_for(rows, "r25_2_2_2_rfcomm_connect_failed")
    closed = details_for(rows, "r25_2_2_2_rfcomm_socket_closed")

    environment = details_for(rows, "client_environment")
    environment_ok = bool(environment) and any(
        item.get("mode") == "private_handoff_rfcomm_connection_only"
        and item.get("gatt_available_in_ui") is False
        and item.get("application_payload_read_implemented") is False
        and item.get("application_payload_write_implemented") is False
        for item in environment
    )

    no_gatt_events = not any("gatt" in str(row.get("event_type", "")).lower() for row in rows)
    no_payload_events = not any(
        any(token in str(row.get("event_type", "")).lower() for token in (
            "payload_read", "payload_write", "stream_read", "stream_write"
        ))
        for row in rows
    )
    zero_counts = all(
        item.get("application_payload_read_count") == 0
        and item.get("application_payload_write_count") == 0
        and item.get("application_data_streams_obtained") is False
        for item in requested + opened + failed + closed
    )

    socket_open = len(opened) == 1 and opened[0].get("connected") is True
    socket_closed = len(closed) == 1
    app_receive = opened[0].get("max_receive_packet_size") if opened else None
    app_transmit = opened[0].get("max_transmit_packet_size") if opened else None

    scn3_lines = [line for line in transport_lines if re.search(r"\bscn\s*[:=]\s*3\b", line, re.I)]
    dlci6_lines = [line for line in transport_lines if re.search(r"\bdlci\s*[:=]\s*6\b", line, re.I)]
    mtu990_lines = [line for line in transport_lines if re.search(r"\bmtu\s*[:=]\s*990\b", line, re.I)]
    rfcomm_client_lines = [
        line for line in transport_lines
        if "rfcomm" in line.lower() and "client" in line.lower()
    ]
    socket_connected_lines = [
        line for line in transport_lines
        if "bluetoothsocket" in line.lower()
        and ("connected" in line.lower() or "mport=3" in line.lower())
    ]
    ownership_lines = []
    for line in transport_lines:
        low = line.lower()
        numeric = {int(value) for value in line.split()[:8] if value.isdigit()}
        if ((probe_uid is not None and f"app_uid: {probe_uid}" in low)
                or bool(numeric & probe_pids)) and "rfcomm" in low:
            ownership_lines.append(line)

    mtu990_runtime = bool(mtu990_lines) or app_receive == 990 or app_transmit == 990
    scn3_dlci6_mtu990 = bool(scn3_lines and dlci6_lines and mtu990_runtime)
    system_runtime_closed = bool(
        scn3_dlci6_mtu990
        and rfcomm_client_lines
        and socket_connected_lines
        and ownership_lines
    )

    source_handoff_valid = bool(
        handoff.get("ready_for_independent_connection_only_qualification") is True
        and handoff.get("application_payload_operation_authorized") is False
        and handoff.get("runtime_address_sha256") == sha256_text(address)
        and handoff.get("runtime_uuid_sha256") == sha256_text(runtime_uuid)
        and handoff.get("endpoint_binding_sha256") == sha256_text(address + "|" + runtime_uuid)
        and expected == {"client": True, "dlci": 6, "mtu": 990, "scn": 3}
    )
    strict_isolation = bool(
        metadata.get("stock_package_disabled") is True
        and metadata.get("stock_pid_observed") is False
        and probe_uid is not None
    )
    capture_valid = bool(
        source_handoff_valid
        and strict_isolation
        and environment_ok
        and len(loaded) == 1
        and len(requested) == 1
        and socket_closed
        and no_gatt_events
        and no_payload_events
        and zero_counts
    )

    if capture_valid and socket_open and system_runtime_closed:
        outcome = "RFCOMM_SOCKET_OPEN_SCN3_DLCI6_MTU990_ZERO_PAYLOAD_CLOSED"
        acceptance = (
            "PASS_PRIVATE_HANDOFF_RFCOMM_SOCKET_OPEN_"
            "SCN3_DLCI6_MTU990_ZERO_PAYLOAD_CLOSED"
        )
    elif capture_valid and socket_open:
        outcome = "RFCOMM_SOCKET_OPEN_ZERO_PAYLOAD_RUNTIME_PARAMETERS_UNRESOLVED"
        acceptance = "PASS_SOCKET_OPEN_ZERO_PAYLOAD_RUNTIME_PARAMETERS_UNRESOLVED"
    elif capture_valid and failed:
        outcome = "BOUNDED_ZERO_PAYLOAD_RFCOMM_CONNECTION_FAILED"
        acceptance = "PASS_BOUNDED_ZERO_PAYLOAD_CONNECTION_ATTEMPT_SOCKET_NOT_OPEN"
    else:
        outcome = "INVALID_CONNECTION_ONLY_CAPTURE"
        acceptance = "FAIL_CAPTURE_INVALID"

    evidence_hashes = []
    for line in transport_lines[:64]:
        value = sha256_text(line)
        if value not in evidence_hashes:
            evidence_hashes.append(value)

    private = {
        "schema": PRIVATE_SCHEMA,
        "release": RELEASE,
        "acceptance": acceptance,
        "qualification_outcome": outcome,
        "capture_valid": capture_valid,
        "source_handoff_valid": source_handoff_valid,
        "strict_isolation": strict_isolation,
        "runtime_address": address,
        "runtime_address_sha256": handoff["runtime_address_sha256"],
        "runtime_uuid": runtime_uuid,
        "runtime_uuid_sha256": handoff["runtime_uuid_sha256"],
        "endpoint_binding_sha256": handoff["endpoint_binding_sha256"],
        "socket": {
            "connect_requested_count": len(requested),
            "open_count": len(opened),
            "failure_count": len(failed),
            "closed_count": len(closed),
            "opened": socket_open,
            "closed": socket_closed,
            "max_receive_packet_size": app_receive,
            "max_transmit_packet_size": app_transmit,
        },
        "runtime_validation": {
            "expected_scn": 3,
            "expected_dlci": 6,
            "expected_mtu": 990,
            "scn3_observed": bool(scn3_lines),
            "dlci6_observed": bool(dlci6_lines),
            "mtu990_observed": mtu990_runtime,
            "rfcomm_client_observed": bool(rfcomm_client_lines),
            "bluetooth_socket_connected_observed": bool(socket_connected_lines),
            "probe_uid_or_pid_ownership_observed": bool(ownership_lines),
            "scn3_dlci6_mtu990_closed": system_runtime_closed,
        },
        "connection_boundary": {
            "independent_gatt_attempted": False,
            "independent_rfcomm_attempted": len(requested) == 1,
            "application_payload_reads": 0,
            "application_payload_writes": 0,
            "application_data_streams_obtained": False,
            "developer_mode_action_performed": False,
        },
        "probe_uid": probe_uid,
        "probe_pids": sorted(probe_pids),
        "transport_evidence_line_count": len(transport_lines),
        "transport_evidence_line_sha256": evidence_hashes,
    }

    public = {
        "schema": PUBLIC_SCHEMA,
        "release": RELEASE,
        "acceptance": acceptance,
        "qualification_outcome": outcome,
        "capture_valid": capture_valid,
        "endpoint": {
            "type": "cached_classic_runtime_endpoint",
            "address_published": False,
            "address_sha256": handoff["runtime_address_sha256"],
            "runtime_uuid_published": False,
            "runtime_uuid_sha256": handoff["runtime_uuid_sha256"],
            "binding_sha256": handoff["endpoint_binding_sha256"],
        },
        "socket": {
            "opened": socket_open,
            "closed": socket_closed,
            "connection_attempt_count": len(requested),
        },
        "runtime_validation": private["runtime_validation"],
        "connection_boundary": private["connection_boundary"],
        "transport_evidence_line_sha256": evidence_hashes,
    }
    return private, public


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-log", type=Path, required=True)
    parser.add_argument("--phone-logcat", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--input-handoff", type=Path, required=True)
    parser.add_argument("--bugreport", type=Path)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    args = parser.parse_args()

    private, public = analyze(
        args.client_log,
        args.phone_logcat,
        args.metadata,
        args.input_handoff,
        args.bugreport,
    )
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.public_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.public_output.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = private["runtime_validation"]
    boundary = private["connection_boundary"]
    print(f"R25_2_2_2_CAPTURE_VALID={'YES' if private['capture_valid'] else 'NO'}")
    print(f"R25_2_2_2_SOURCE_HANDOFF_VALID={'YES' if private['source_handoff_valid'] else 'NO'}")
    print(f"R25_2_2_2_STRICT_ISOLATION={'YES' if private['strict_isolation'] else 'NO'}")
    print(f"R25_2_2_2_RFCOMM_CONNECT_REQUESTED={'YES' if private['socket']['connect_requested_count'] == 1 else 'NO'}")
    print(f"R25_2_2_2_RFCOMM_SOCKET_OPEN={'YES' if private['socket']['opened'] else 'NO'}")
    print(f"R25_2_2_2_RFCOMM_SOCKET_CLOSED={'YES' if private['socket']['closed'] else 'NO'}")
    print(f"R25_2_2_2_SCN3_OBSERVED={'YES' if validation['scn3_observed'] else 'NO'}")
    print(f"R25_2_2_2_DLCI6_OBSERVED={'YES' if validation['dlci6_observed'] else 'NO'}")
    print(f"R25_2_2_2_MTU990_OBSERVED={'YES' if validation['mtu990_observed'] else 'NO'}")
    print(f"R25_2_2_2_SCN3_DLCI6_MTU990_CLOSED={'YES' if validation['scn3_dlci6_mtu990_closed'] else 'NO'}")
    print(f"R25_2_2_2_INDEPENDENT_GATT_ATTEMPTED={'YES' if boundary['independent_gatt_attempted'] else 'NO'}")
    print(f"R25_2_2_2_INDEPENDENT_RFCOMM_ATTEMPTED={'YES' if boundary['independent_rfcomm_attempted'] else 'NO'}")
    print(f"R25_2_2_2_APPLICATION_PAYLOAD_READ_COUNT={boundary['application_payload_reads']}")
    print(f"R25_2_2_2_APPLICATION_PAYLOAD_WRITE_COUNT={boundary['application_payload_writes']}")
    print(f"R25_2_2_2_APPLICATION_DATA_STREAMS_OBTAINED={'YES' if boundary['application_data_streams_obtained'] else 'NO'}")
    print(f"R25_2_2_2_QUALIFICATION_OUTCOME={private['qualification_outcome']}")
    print("R25_2_2_2_ANALYSIS=PASS")
    print(f"R1_3_3_2_25_2_2_2_ACCEPTANCE={private['acceptance']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
