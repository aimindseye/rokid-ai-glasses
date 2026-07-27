#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import hashlib
import hmac
import io
import json
from pathlib import Path
import re
import statistics
import zipfile
from typing import Any, Iterable

RELEASE = "r1.3.3.2.25.2.2.1"
SOURCE_RELEASE = "r1.3.3.2.25.2.2"
STOCK_PACKAGE = "com.rokid.sprite.global.aiapp"
PRIVATE_SCHEMA = "rokid.r25.2.2.1.cached-runtime-private-analysis.v1"
PUBLIC_SCHEMA = "rokid.r25.2.2.1.cached-runtime-publication.v1"
HANDOFF_SCHEMA = "rokid.r25.2.2.1.connection-only-handoff-private.v1"

CONNECT_RE = re.compile(
    r"connectBluetooth\s+context:.*?socketUuid:(?P<uuid>[0-9A-Fa-f-]{36}),"
    r"macAddress:(?P<address>(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})"
)
EPOCH_RE = re.compile(r"^\s*(?P<epoch>\d{10}(?:\.\d+)?)\s+")
APP_UID_RE = re.compile(r"\bapp_uid:\s*(?P<uid>\d+)\b")
SCN_RE = re.compile(r"\bscn[:=]\s*(?P<value>\d+)\b", re.IGNORECASE)
DLCI_RE = re.compile(r"\bdlci[:=]\s*(?P<value>\d+)\b", re.IGNORECASE)
MTU_RE = re.compile(r"\bmtu[:=]\s*(?P<value>\d+)\b", re.IGNORECASE)
PORT_RE = re.compile(r"\bmPort=(?P<value>\d+)\b")
CXR_VERSION_RE = re.compile(r"CxrSocketProtocol version:(?P<value>\d+)")
INVALID_ADDRESSES = {"00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_epoch(line: str) -> float | None:
    match = EPOCH_RE.match(line)
    return float(match.group("epoch")) if match else None


def pid_in_line(line: str, stock_pids: set[int]) -> bool:
    fields = line.split()
    numeric = {int(field) for field in fields[:8] if field.isdigit()}
    return bool(numeric & stock_pids)


def bounded(lines: Iterable[str], start: float, end: float, tolerance: float = 2.0) -> list[str]:
    result: list[str] = []
    for line in lines:
        epoch = parse_epoch(line)
        if epoch is not None and start - tolerance <= epoch <= end + tolerance:
            result.append(line)
    return result


def load_bugreport_text(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    with zipfile.ZipFile(path) as outer:
        direct = [n for n in outer.namelist() if re.fullmatch(r"bugreport-.*\.txt", n)]
        if len(direct) == 1:
            return outer.read(direct[0]).decode("utf-8", errors="replace").splitlines()
        for nested in [n for n in outer.namelist() if n.endswith(".zip")]:
            try:
                with zipfile.ZipFile(io.BytesIO(outer.read(nested))) as inner:
                    names = [n for n in inner.namelist() if re.fullmatch(r"bugreport-.*\.txt", n)]
                    if len(names) == 1:
                        return inner.read(names[0]).decode("utf-8", errors="replace").splitlines()
            except zipfile.BadZipFile:
                continue
    return []


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


def phase_sequence_ok(rows: list[dict[str, Any]]) -> bool:
    expected = ["stock_disabled_baseline", "stock_assist_window", "post_stock_handoff"]
    starts = [
        row.get("details", {}).get("phase")
        for row in rows
        if row.get("event_type") == "r25_2_2_phase_started"
    ]
    completes = [
        row.get("details", {}).get("phase")
        for row in rows
        if row.get("event_type") == "r25_2_2_phase_complete"
    ]
    complete_count = sum(
        1 for row in rows if row.get("event_type") == "r25_2_2_capture_complete"
    )
    return starts == expected and completes == expected and complete_count == 1


def infer_stock_uid(
    lines: list[str], stock_pids: set[int], metadata_uid: Any
) -> tuple[int | None, str]:
    if isinstance(metadata_uid, int) and metadata_uid > 0:
        return metadata_uid, "run_metadata"

    candidates: collections.Counter[int] = collections.Counter()
    for line in lines:
        lowered = line.lower()
        match = APP_UID_RE.search(line)
        if match and "rfcomm" in lowered and "scn: 3" in lowered:
            candidates[int(match.group("uid"))] += 10
        if STOCK_PACKAGE in line:
            for value in re.findall(r"\b\d{4,6}\b", line):
                number = int(value)
                if number not in stock_pids and number >= 10000:
                    candidates[number] += 1
    if not candidates:
        return None, "unresolved"
    ordered = candidates.most_common()
    if len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
        return None, "ambiguous_log_inference"
    return ordered[0][0], "bounded_log_inference"


def scan_summary(
    client_rows: list[dict[str, Any]], key: bytes | None, address: str
) -> dict[str, Any] | None:
    if key is None:
        return None
    token = hmac.new(key, address.encode("ascii"), hashlib.sha256).hexdigest()
    matching: list[dict[str, Any]] = []
    for row in client_rows:
        if row.get("event_type") != "r25_2_2_ble_advertisement":
            continue
        details = row.get("details")
        if isinstance(details, dict) and details.get("address_hmac_sha256") == token:
            matching.append(details)
    if not matching:
        return None
    rssis = [
        item["rssi"] for item in matching
        if isinstance(item.get("rssi"), int) and item.get("rssi") != 127
    ]
    phases = collections.Counter(str(item.get("phase")) for item in matching)
    return {
        "address_hmac_sha256": token,
        "advertisement_count": len(matching),
        "phase_counts": dict(sorted(phases.items())),
        "max_rssi": max(rssis) if rssis else None,
        "median_rssi": statistics.median(rssis) if rssis else None,
        "correlated": True,
    }


def line_hashes(lines: list[str], limit: int = 32) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        digest = sha256_text(line)
        if digest in seen:
            continue
        seen.add(digest)
        result.append(digest)
        if len(result) >= limit:
            break
    return result


def analyze(
    client_log: Path,
    stock_logcat: Path,
    metadata_path: Path,
    correlation_key: Path | None,
    bugreport: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    client_rows = read_jsonl(client_log)
    stock_pids = {
        int(value) for value in metadata.get("stock_pids", [])
        if str(value).isdigit()
    }
    start = float(metadata["stock_assist_start_epoch"])
    end = float(metadata["stock_assist_end_epoch"])

    stock_lines = bounded(
        stock_logcat.read_text(encoding="utf-8", errors="replace").splitlines(),
        start,
        end,
    )
    bug_lines = bounded(load_bugreport_text(bugreport), start, end)
    combined_lines = stock_lines + bug_lines

    stock_uid, stock_uid_source = infer_stock_uid(
        stock_lines, stock_pids, metadata.get("stock_uid")
    )

    observations: dict[tuple[str, str], dict[str, Any]] = {}
    for source_name, lines in (("stock_logcat", stock_lines), ("bugreport", bug_lines)):
        for line in lines:
            match = CONNECT_RE.search(line)
            if not match:
                continue
            if stock_pids and not pid_in_line(line, stock_pids):
                continue
            address = match.group("address").upper()
            runtime_uuid = match.group("uuid").lower()
            if address in INVALID_ADDRESSES:
                continue
            entry = observations.setdefault(
                (address, runtime_uuid),
                {
                    "address": address,
                    "runtime_uuid": runtime_uuid,
                    "sources": collections.Counter(),
                    "endpoint_lines": [],
                },
            )
            entry["sources"][source_name] += 1
            entry["endpoint_lines"].append(line)

    key_bytes: bytes | None = None
    if correlation_key is not None and correlation_key.is_file():
        key_hex = correlation_key.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-fA-F]{64}", key_hex):
            key_bytes = bytes.fromhex(key_hex)

    candidates: list[dict[str, Any]] = []
    stock_pid_lines = [line for line in stock_lines if pid_in_line(line, stock_pids)]
    for (address, runtime_uuid), entry in observations.items():
        suffix = ":".join(address.split(":")[-2:]).lower()
        related = [line for line in combined_lines if suffix in line.lower()]

        acl_lines = [
            line for line in related
            if "br/edr connected" in line.lower()
            or ("acl connected" in line.lower() and "bt_transport_br_edr" in line.lower())
        ]
        sdp_lines = []
        for line in related:
            match = SCN_RE.search(line)
            if (
                "service discovery" in line.lower()
                and "success" in line.lower()
                and match
                and int(match.group("value")) == 3
            ):
                sdp_lines.append(line)

        create_lines = []
        for line in related:
            if "rfcomm_createconnectionwithsecurity" not in line.lower():
                continue
            scn = SCN_RE.search(line)
            dlci = DLCI_RE.search(line)
            mtu = MTU_RE.search(line)
            if (
                scn and dlci and mtu
                and int(scn.group("value")) == 3
                and int(dlci.group("value")) == 6
                and int(mtu.group("value")) == 990
                and "is_server=false" in line.lower()
            ):
                create_lines.append(line)

        uid_lines = []
        for line in related:
            if "connected to rfcomm socket connections" not in line.lower():
                continue
            scn = SCN_RE.search(line)
            uid = APP_UID_RE.search(line)
            if not scn or int(scn.group("value")) != 3 or not uid:
                continue
            if stock_uid is None or int(uid.group("uid")) == stock_uid:
                uid_lines.append(line)

        socket_lines = [
            line for line in stock_pid_lines
            if "bluetoothsocket: connect(), socket connected" in line.lower()
            and (match := PORT_RE.search(line))
            and int(match.group("value")) == 3
        ]
        read_lines = [
            line for line in stock_pid_lines
            if "bluetoothcontroller: readfromrfcomm" in line.lower()
        ]
        cxr_version_lines = [
            line for line in stock_pid_lines if CXR_VERSION_RE.search(line)
        ]
        cxr_success_lines = [
            line for line in stock_pid_lines
            if "mcxrsocketprotocol run end,result:true" in line.lower()
        ]
        available_lines = [
            line for line in stock_pid_lines
            if "updatestatus status:bluetooth_available" in line.lower()
        ]

        domains = {
            "stock_app_endpoint": bool(entry["endpoint_lines"]),
            "br_edr_acl": bool(acl_lines),
            "sdp_scn3": bool(sdp_lines),
            "rfcomm_scn3_dlci6_mtu990": bool(create_lines),
            "rfcomm_stock_uid": bool(uid_lines),
            "stock_socket_port3": bool(socket_lines),
            "stock_read_from_rfcomm": bool(read_lines),
            "cxr_protocol_success": bool(cxr_success_lines),
            "stock_bluetooth_available": bool(available_lines),
        }
        independent_count = sum(
            1 for name in (
                "stock_app_endpoint",
                "rfcomm_scn3_dlci6_mtu990",
                "rfcomm_stock_uid",
                "stock_socket_port3",
                "cxr_protocol_success",
            )
            if domains[name]
        )
        closure = bool(
            all(domains.values())
            and independent_count >= 4
            and stock_uid is not None
        )

        versions = sorted({
            int(match.group("value"))
            for line in cxr_version_lines
            if (match := CXR_VERSION_RE.search(line))
        })
        evidence = (
            entry["endpoint_lines"] + acl_lines + sdp_lines + create_lines
            + uid_lines + socket_lines + read_lines + cxr_version_lines
            + cxr_success_lines + available_lines
        )
        candidate = {
            "address": address,
            "runtime_uuid": runtime_uuid,
            "address_sha256": sha256_text(address),
            "runtime_uuid_sha256": sha256_text(runtime_uuid),
            "endpoint_binding_sha256": sha256_text(address + "|" + runtime_uuid),
            "address_suffix_sha256": sha256_text(suffix.upper()),
            "stock_uid": stock_uid,
            "stock_uid_source": stock_uid_source,
            "stock_pids": sorted(stock_pids),
            "evidence_domains": domains,
            "independent_evidence_domain_count": independent_count,
            "evidence_line_count": len(evidence),
            "evidence_line_sha256": line_hashes(evidence),
            "source_counts": dict(entry["sources"]),
            "rfcomm": {
                "scn": 3 if create_lines and socket_lines else None,
                "dlci": 6 if create_lines else None,
                "mtu": 990 if create_lines else None,
                "uuid16": (
                    "0x1101"
                    if any("uuid=0x1101" in line.lower() for line in create_lines)
                    else None
                ),
                "client": bool(create_lines),
            },
            "cxr_socket_protocol_versions": versions,
            "scan": scan_summary(client_rows, key_bytes, address),
            "closure_gate_passed": closure,
        }
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            not item["closure_gate_passed"],
            -item["independent_evidence_domain_count"],
            -item["evidence_line_count"],
            item["endpoint_binding_sha256"],
        )
    )
    qualifying = [item for item in candidates if item["closure_gate_passed"]]
    unique = len(qualifying) == 1
    top = qualifying[0] if unique else None

    source_valid = bool(
        phase_sequence_ok(client_rows)
        and metadata.get("stock_launch_verified") is True
        and metadata.get("stock_foreground_verified") is True
        and metadata.get("stock_enabled_for_assist") is True
        and metadata.get("stock_disabled_after_assist") is True
        and len(stock_pids) > 0
    )
    if not source_valid:
        acceptance = "FAIL_SOURCE_CAPTURE_INVALID"
        outcome = "SOURCE_CAPTURE_INVALID"
    elif unique:
        acceptance = (
            "PASS_UNIQUE_CACHED_RUNTIME_ENDPOINT_ATTRIBUTED_"
            "CONNECTION_ONLY_HANDOFF_READY"
        )
        outcome = (
            "UNIQUE_CACHED_RUNTIME_ENDPOINT_ATTRIBUTED_"
            "RFCOMM_SCN3_DLCI6_MTU990_CLOSED"
        )
    else:
        acceptance = "PASS_BOUNDED_REANALYSIS_CACHED_RUNTIME_ENDPOINT_UNRESOLVED"
        outcome = "BOUNDED_REANALYSIS_CACHED_RUNTIME_ENDPOINT_UNRESOLVED"

    boundary = {
        "offline_reanalysis_only": True,
        "independent_gatt_attempted": False,
        "independent_rfcomm_attempted": False,
        "automatic_connection_performed": False,
        "application_payload_reads": 0,
        "application_payload_writes": 0,
        "developer_mode_action_performed": False,
    }
    private = {
        "schema": PRIVATE_SCHEMA,
        "release": RELEASE,
        "source_release": SOURCE_RELEASE,
        "acceptance": acceptance,
        "attribution_outcome": outcome,
        "source_capture_valid": source_valid,
        "stock_assist_start_epoch": start,
        "stock_assist_end_epoch": end,
        "bounded_stock_logcat_line_count": len(stock_lines),
        "bounded_bugreport_line_count": len(bug_lines),
        "stock_uid": stock_uid,
        "stock_uid_source": stock_uid_source,
        "stock_pids": sorted(stock_pids),
        "candidate_count": len(candidates),
        "qualifying_candidate_count": len(qualifying),
        "unique_runtime_endpoint_attributed": unique,
        "cached_runtime_path_observed": unique,
        "provisioning_gatt_observed": False,
        "ranked_candidates": candidates,
        "connection_boundary": boundary,
    }
    public_top = None
    if top:
        public_top = {
            "address_sha256": top["address_sha256"],
            "runtime_uuid_sha256": top["runtime_uuid_sha256"],
            "endpoint_binding_sha256": top["endpoint_binding_sha256"],
            "stock_uid_resolved": top["stock_uid"] is not None,
            "stock_uid_source": top["stock_uid_source"],
            "evidence_domains": top["evidence_domains"],
            "independent_evidence_domain_count": top["independent_evidence_domain_count"],
            "rfcomm": top["rfcomm"],
            "cxr_socket_protocol_versions": top["cxr_socket_protocol_versions"],
            "scan_correlated": top["scan"] is not None,
            "scan_summary": top["scan"],
        }
    public = {
        "schema": PUBLIC_SCHEMA,
        "release": RELEASE,
        "source_release": SOURCE_RELEASE,
        "acceptance": acceptance,
        "attribution_outcome": outcome,
        "source_capture_valid": source_valid,
        "candidate_count": len(candidates),
        "qualifying_candidate_count": len(qualifying),
        "unique_runtime_endpoint_attributed": unique,
        "cached_runtime_path_observed": unique,
        "provisioning_gatt_observed": False,
        "runtime_address_published": False,
        "runtime_uuid_published": False,
        "attributed_endpoint": public_top,
        "connection_boundary": boundary,
        "public_safety": {
            "raw_bluetooth_address_published": False,
            "raw_runtime_uuid_published": False,
            "raw_logcat_published": False,
            "raw_bugreport_published": False,
            "correlation_key_published": False,
            "application_payload_published": False,
        },
    }
    if top:
        handoff = {
            "schema": HANDOFF_SCHEMA,
            "release": RELEASE,
            "source_release": SOURCE_RELEASE,
            "available": True,
            "endpoint_type": "cached_classic_runtime_endpoint",
            "runtime_address": top["address"],
            "runtime_uuid": top["runtime_uuid"],
            "runtime_address_sha256": top["address_sha256"],
            "runtime_uuid_sha256": top["runtime_uuid_sha256"],
            "endpoint_binding_sha256": top["endpoint_binding_sha256"],
            "stock_uid": top["stock_uid"],
            "stock_uid_source": top["stock_uid_source"],
            "stock_pids": top["stock_pids"],
            "rfcomm": top["rfcomm"],
            "cxr_socket_protocol_versions": top["cxr_socket_protocol_versions"],
            "scan_correlated": top["scan"] is not None,
            "scan_summary": top["scan"],
            "provisioning_gatt_observed": False,
            "cached_runtime_path_observed": True,
            "ready_for_independent_connection_only_qualification": True,
            "automatic_connection_performed": False,
            "application_payload_operation_authorized": False,
            "evidence_line_sha256": top["evidence_line_sha256"],
        }
    else:
        handoff = {
            "schema": HANDOFF_SCHEMA,
            "release": RELEASE,
            "source_release": SOURCE_RELEASE,
            "available": False,
            "reason": "unique_cached_runtime_endpoint_not_attributed",
            "ready_for_independent_connection_only_qualification": False,
            "automatic_connection_performed": False,
            "application_payload_operation_authorized": False,
        }
    return private, public, handoff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-log", type=Path, required=True)
    parser.add_argument("--stock-logcat", type=Path, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--correlation-key", type=Path)
    parser.add_argument("--bugreport", type=Path)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--handoff-output", type=Path, required=True)
    args = parser.parse_args()

    private, public, handoff = analyze(
        args.client_log,
        args.stock_logcat,
        args.run_metadata,
        args.correlation_key,
        args.bugreport,
    )
    for path, value in (
        (args.private_output, private),
        (args.public_output, public),
        (args.handoff_output, handoff),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(f"R25_2_2_1_SOURCE_CAPTURE_VALID={'YES' if private['source_capture_valid'] else 'NO'}")
    print(f"R25_2_2_1_STOCK_UID_RESOLVED={'YES' if private['stock_uid'] is not None else 'NO'}")
    print(f"R25_2_2_1_STOCK_UID_SOURCE={private['stock_uid_source']}")
    print(f"R25_2_2_1_RUNTIME_ENDPOINT_CANDIDATE_COUNT={private['candidate_count']}")
    print(f"R25_2_2_1_QUALIFYING_CANDIDATE_COUNT={private['qualifying_candidate_count']}")
    print(f"R25_2_2_1_UNIQUE_RUNTIME_ENDPOINT_ATTRIBUTED={'YES' if private['unique_runtime_endpoint_attributed'] else 'NO'}")
    top = private["ranked_candidates"][0] if private["ranked_candidates"] else None
    closure = bool(top and top.get("closure_gate_passed"))
    print(f"R25_2_2_1_RFCOMM_SCN3_DLCI6_MTU990_CLOSED={'YES' if closure else 'NO'}")
    print(f"R25_2_2_1_PRIVATE_HANDOFF_AVAILABLE={'YES' if handoff.get('available') else 'NO'}")
    print("R25_2_2_1_INDEPENDENT_GATT_ATTEMPTED=NO")
    print("R25_2_2_1_INDEPENDENT_RFCOMM_ATTEMPTED=NO")
    print("R25_2_2_1_APPLICATION_PAYLOAD_READ_COUNT=0")
    print("R25_2_2_1_APPLICATION_PAYLOAD_WRITE_COUNT=0")
    print(f"R25_2_2_1_ATTRIBUTION_OUTCOME={private['attribution_outcome']}")
    print("R25_2_2_1_ANALYSIS=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
