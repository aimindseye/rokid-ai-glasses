#!/usr/bin/env python3
"""R25.2.3.1 offline qualification for an instrumented Android RFCOMM capture.

The analyzer proves zero application payload only from a complete, lossless HCI
RFCOMM DLCI frame census. Logcat silence is retained as corroboration, never as
proof. Standard library only.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

RELEASE = "r1.3.3.2.25.2.3.1"
SCHEMA_PRIVATE = "rokid.r25.2.3.1.private-analysis.v1"
SCHEMA_PUBLIC = "rokid.r25.2.3.1.publication.v1"
BTSNOOP_EPOCH_DELTA_US = 0x00DC_DDB3_0F2F_8000
UTC = dt.timezone.utc


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_zip_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise RuntimeError(f"refusing symlink in output tree: {path}")
            if path.is_file():
                zf.write(path, path.relative_to(source.parent).as_posix())


@dataclasses.dataclass
class LogRecord:
    timestamp: dt.datetime
    event: str
    raw: str
    fields: Dict[str, Any]


EPOCH_LINE = re.compile(r"^\s*(?P<epoch>\d{10}(?:\.\d{1,9})?)\s+\d+\s+\d+\s+[VDIWEF]\s+(?P<tag>[^:]+):\s*(?P<body>.*)$")
ADDR = r"[0-9A-Fa-fXx]{2}(?::[0-9A-Fa-fXx]{2}){5}"
UUID128 = r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"


def field_int(body: str, names: Sequence[str]) -> Optional[int]:
    for name in names:
        m = re.search(rf"(?i)\b{re.escape(name)}\s*[:=]\s*(-?\d+)", body)
        if m:
            return int(m.group(1))
    return None


def field_text(body: str, names: Sequence[str], pattern: str) -> Optional[str]:
    for name in names:
        m = re.search(rf"(?i)\b{re.escape(name)}\s*[:=]\s*({pattern})", body)
        if m:
            return m.group(1).lower()
    return None


def classify_log_line(line: str, start: dt.datetime, end: dt.datetime) -> Optional[LogRecord]:
    m = EPOCH_LINE.match(line)
    if not m:
        return None
    ts = dt.datetime.fromtimestamp(float(m.group("epoch")), tz=UTC)
    if ts < start or ts > end:
        return None
    body = f"{m.group('tag').strip()}: {m.group('body').strip()}"
    lower = body.lower()
    fields: Dict[str, Any] = {}
    event: Optional[str] = None

    if "connectsocket" in lower and "from uid/pid" in lower:
        event = "connect_request"
        fields["endpoint"] = field_text(body, ["device"], ADDR)
        fields["requested_service_uuid"] = field_text(body, ["uuid"], UUID128)
        pair = re.search(r"(?i)from\s+uid/pid\s*=\s*(\d+)\s*/\s*(\d+)", body)
        if pair:
            fields["uid"], fields["pid"] = int(pair.group(1)), int(pair.group(2))
    elif "btsock_rfc_connect" in lower:
        event = "rfcomm_socket_request"
        fields["endpoint"] = field_text(body, ["bd_addr", "device"], ADDR)
        fields["requested_service_uuid"] = field_text(body, ["service_uuid", "uuid"], UUID128)
        fields["slot"] = field_int(body, ["slot_id", "id"])
    elif "rfcomm_createconnectionwithsecurity" in lower:
        event = "native_create"
        fields["endpoint"] = field_text(body, ["bd_addr", "device"], ADDR)
        for key, names in {
            "scn": ["scn"], "dlci": ["dlci"], "mtu": ["mtu"], "port_handle": ["port_handle"]
        }.items():
            fields[key] = field_int(body, names)
        m_uuid = re.search(r"(?i)\buuid\s*[:=]\s*(0x[0-9a-f]+)", body)
        if m_uuid:
            fields["native_service_class_uuid"] = m_uuid.group(1).lower()
        server = re.search(r"(?i)\bis_server\s*[:=]\s*(true|false|0|1)", body)
        if server:
            fields["is_server"] = server.group(1).lower() in {"true", "1"}
    elif "rfc_port_event_close" in lower:
        event = "port_close_event"
        for key, names in {"scn": ["scn"], "dlci": ["dlci"], "port_handle": ["port_handle"]}.items():
            fields[key] = field_int(body, names)
    elif "rfc_port_event_open" in lower:
        event = "port_open_event"
        for key, names in {"scn": ["scn"], "dlci": ["dlci"], "port_handle": ["port_handle"]}.items():
            fields[key] = field_int(body, names)
    elif "bta_jv_rfcomm_open_evt" in lower:
        event = "jv_open_event"
        fields["slot"] = field_int(body, ["slot_id", "id"])
        fields["port_handle"] = field_int(body, ["port_handle", "handle"])
    elif "on_cli_rfc_connect" in lower or ("rfcomm" in lower and "is_server=false" in lower and "connected" in lower):
        event = "client_connected"
        fields["endpoint"] = field_text(body, ["device", "bd_addr"], ADDR)
        fields["uid"] = field_int(body, ["app_uid", "uid"])
        fields["slot"] = field_int(body, ["slot_id", "id"])
        fields["scn"] = field_int(body, ["scn"])
        fields["socket_id"] = field_int(body, ["socket_id"])
    elif "bluetoothsocket" in lower and "connected" in lower:
        event = "socket_connected"
        fields["endpoint"] = field_text(body, ["device"], ADDR)
        fields["uid"] = field_int(body, ["uid"])
        fields["pid"] = field_int(body, ["pid"])
    elif "cleanup_rfc_slot" in lower:
        event = "slot_cleanup"
        fields["endpoint"] = field_text(body, ["device", "bd_addr"], ADDR)
        fields["uid"] = field_int(body, ["app_uid", "uid"])
        fields["slot"] = field_int(body, ["slot_id", "id"])
        fields["scn"] = field_int(body, ["scn"])
        fields["socket_id"] = field_int(body, ["socket_id"])
    elif "port_rfc_closed" in lower or "bta_jv_rfcomm_close" in lower:
        event = "native_close"
        fields["endpoint"] = field_text(body, ["device", "bd_addr"], ADDR)
        fields["port_handle"] = field_int(body, ["port_handle", "handle"])
        fields["scn"] = field_int(body, ["scn"])
        fields["dlci"] = field_int(body, ["dlci"])
        server = re.search(r"(?i)\bis_server\s*[:=]\s*(true|false|0|1)", body)
        if server:
            fields["is_server"] = server.group(1).lower() in {"true", "1"}
    elif re.search(r"(?i)(rfcomm|bta_jv).*(data|rxchar|write|read).*(?:len|bytes|size)\s*[:=]\s*[1-9]\d*", body):
        event = "positive_payload_event"
        fields["length"] = field_int(body, ["len", "bytes", "size"])
    if event is None:
        return None
    fields = {k: v for k, v in fields.items() if v is not None}
    return LogRecord(timestamp=ts, event=event, raw=line.rstrip("\n"), fields=fields)


def canonical_log_key(record: LogRecord) -> Tuple[Any, ...]:
    return (round(record.timestamp.timestamp(), 3), record.event, tuple(sorted(record.fields.items())))


def parse_logcat(path: Path, start: dt.datetime, end: dt.datetime) -> List[LogRecord]:
    records: List[LogRecord] = []
    seen = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rec = classify_log_line(line, start, end)
        if rec is None:
            continue
        key = canonical_log_key(rec)
        if key in seen:
            continue
        seen.add(key)
        records.append(rec)
    return sorted(records, key=lambda r: r.timestamp)


def unique_value(records: Sequence[LogRecord], key: str) -> Tuple[Optional[Any], List[Any]]:
    values = sorted({r.fields[key] for r in records if key in r.fields}, key=str)
    return (values[0] if len(values) == 1 else None, values)


def reconstruct_lifecycle(records: Sequence[LogRecord]) -> Dict[str, Any]:
    starts = [r for r in records if r.event == "connect_request"]
    if len(starts) != 1:
        return {"proven": False, "reasons": [f"connect_request_count={len(starts)}"], "records": [dataclasses.asdict(r) for r in records]}
    root = starts[0]
    closes = [r for r in records if r.event in {"port_close_event", "native_close"} and r.timestamp >= root.timestamp]
    if not closes:
        return {"proven": False, "reasons": ["missing_explicit_transport_close"], "records": [dataclasses.asdict(r) for r in records]}
    end = max(r.timestamp for r in closes)
    selected = [r for r in records if root.timestamp <= r.timestamp <= end]
    fields: Dict[str, Any] = {}
    conflicts: Dict[str, List[Any]] = {}
    for key in ("endpoint", "requested_service_uuid", "uid", "pid", "slot", "port_handle", "scn", "dlci", "mtu", "native_service_class_uuid"):
        value, values = unique_value(selected, key)
        if value is not None:
            fields[key] = value
        elif values:
            conflicts[key] = values
    events = {r.event for r in selected}
    client_semantic = any(r.event == "client_connected" for r in selected) and any(r.event == "native_create" and r.fields.get("is_server") is False for r in selected)
    open_ok = bool(events & {"port_open_event", "jv_open_event", "client_connected"})
    close_ok = "port_close_event" in events and bool(events & {"native_close", "slot_cleanup"})
    required = ("endpoint", "requested_service_uuid", "uid", "pid", "slot", "port_handle", "scn", "dlci", "mtu")
    tuple_complete = all(k in fields for k in required)
    positive_logcat = [r for r in selected if r.event == "positive_payload_event" and int(r.fields.get("length", 0)) > 0]
    proven = client_semantic and open_ok and close_ok and tuple_complete and not conflicts
    reasons: List[str] = []
    if not client_semantic: reasons.append("client_semantic_not_proven")
    if not open_ok: reasons.append("open_not_proven")
    if not close_ok: reasons.append("matching_close_not_proven")
    if not tuple_complete: reasons.append("runtime_tuple_incomplete")
    if conflicts: reasons.append("runtime_tuple_conflict")
    return {
        "proven": proven,
        "reasons": reasons,
        "start_utc": iso_utc(root.timestamp),
        "end_utc": iso_utc(end),
        "fields": fields,
        "conflicts": conflicts,
        "client_semantic": client_semantic,
        "matching_open_close": open_ok and close_ok,
        "tuple_complete": tuple_complete,
        "positive_logcat_payload_event_count": len(positive_logcat),
        "no_logcat_payload_event_observed": len(positive_logcat) == 0,
        "records": [{"timestamp_utc": iso_utc(r.timestamp), "event": r.event, "fields": r.fields, "raw": r.raw} for r in selected],
    }


@dataclasses.dataclass
class BtsnoopRecord:
    timestamp: dt.datetime
    flags: int
    drops: int
    original_length: int
    included_length: int
    packet: bytes


@dataclasses.dataclass
class L2capPdu:
    timestamp: dt.datetime
    direction: str
    handle: int
    cid: int
    payload: bytes
    source_record_index: int


@dataclasses.dataclass
class RfcommFrame:
    timestamp: dt.datetime
    direction: str
    handle: int
    cid: int
    dlci: int
    frame_type: str
    information_length: int
    payload_hex: str


def parse_btsnoop(data: bytes) -> Tuple[int, List[BtsnoopRecord], List[str]]:
    if len(data) < 16 or data[:8] != b"btsnoop\x00":
        raise ValueError("invalid btsnoop header")
    version, datalink = struct.unpack(">II", data[8:16])
    if version != 1:
        raise ValueError(f"unsupported btsnoop version {version}")
    pos = 16
    records: List[BtsnoopRecord] = []
    errors: List[str] = []
    while pos < len(data):
        if pos + 24 > len(data):
            errors.append("truncated_record_header")
            break
        original, included, flags, drops, timestamp_raw = struct.unpack(">IIIIQ", data[pos:pos+24])
        pos += 24
        if pos + included > len(data):
            errors.append("truncated_record_payload")
            break
        packet = data[pos:pos+included]
        pos += included
        unix_us = timestamp_raw - BTSNOOP_EPOCH_DELTA_US
        ts = dt.datetime.fromtimestamp(unix_us / 1_000_000, tz=UTC)
        records.append(BtsnoopRecord(ts, flags, drops, original, included, packet))
    return datalink, records, errors


def acl_packet(packet: bytes, datalink: int) -> Optional[Tuple[int, int, bytes]]:
    # Android bugreports normally use HCI UART (H4), datalink 1002.
    if datalink == 1002:
        if len(packet) < 5 or packet[0] != 0x02:
            return None
        offset = 1
    elif datalink in {1001, 2010}:
        if len(packet) < 4:
            return None
        offset = 0
    else:
        return None
    handle_flags, total = struct.unpack_from("<HH", packet, offset)
    payload = packet[offset+4:offset+4+total]
    if len(payload) != total:
        return None
    handle = handle_flags & 0x0FFF
    pb = (handle_flags >> 12) & 0x3
    return handle, pb, payload


def reassemble_l2cap(datalink: int, records: Sequence[BtsnoopRecord]) -> Tuple[List[L2capPdu], List[str]]:
    pending: Dict[Tuple[str, int], Dict[str, Any]] = {}
    pdus: List[L2capPdu] = []
    errors: List[str] = []
    for index, rec in enumerate(records):
        parsed = acl_packet(rec.packet, datalink)
        if parsed is None:
            continue
        handle, pb, payload = parsed
        direction = "rx" if (rec.flags & 1) else "tx"
        key = (direction, handle)
        if pb in {0, 2, 3}:
            if len(payload) < 4:
                errors.append(f"short_l2cap_start:{index}")
                continue
            length, cid = struct.unpack_from("<HH", payload, 0)
            pending[key] = {"expected": 4 + length, "data": bytearray(payload), "timestamp": rec.timestamp, "cid": cid, "index": index}
        elif pb == 1:
            if key not in pending:
                errors.append(f"orphan_acl_continuation:{index}")
                continue
            pending[key]["data"].extend(payload)
        else:
            errors.append(f"unsupported_pb_flag:{pb}")
            continue
        state = pending.get(key)
        if state and len(state["data"]) >= state["expected"]:
            blob = bytes(state["data"][:state["expected"]])
            length, cid = struct.unpack_from("<HH", blob, 0)
            pdus.append(L2capPdu(state["timestamp"], direction, handle, cid, blob[4:4+length], state["index"]))
            if len(state["data"]) > state["expected"]:
                errors.append(f"l2cap_overrun:{index}")
            del pending[key]
    if pending:
        errors.extend(f"incomplete_l2cap_pdu:{direction}:{handle}" for direction, handle in pending)
    return pdus, errors


def discover_rfcomm_cids(pdus: Sequence[L2capPdu]) -> Dict[int, set[int]]:
    cids: Dict[int, set[int]] = defaultdict(set)
    pending: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for pdu in pdus:
        if pdu.cid != 0x0001:
            continue
        pos = 0
        while pos + 4 <= len(pdu.payload):
            code, ident, length = struct.unpack_from("<BBH", pdu.payload, pos)
            params = pdu.payload[pos+4:pos+4+length]
            pos += 4 + length
            if len(params) != length:
                break
            if code == 0x02 and length >= 4:  # Connection Request
                psm, scid = struct.unpack_from("<HH", params, 0)
                pending[(pdu.handle, ident)] = (psm, scid)
                if psm == 0x0003:
                    cids[pdu.handle].add(scid)
            elif code == 0x03 and length >= 8:  # Connection Response
                dcid, scid, result, _status = struct.unpack_from("<HHHH", params, 0)
                request = pending.get((pdu.handle, ident))
                if (request and request[0] == 0x0003) or dcid in cids[pdu.handle]:
                    if result == 0:
                        cids[pdu.handle].update({dcid, scid})
    return cids


def parse_rfcomm_frames(pdu: L2capPdu) -> Tuple[List[RfcommFrame], List[str]]:
    data = pdu.payload
    pos = 0
    frames: List[RfcommFrame] = []
    errors: List[str] = []
    while pos < len(data):
        frame_start = pos
        if len(data) - pos < 4:
            errors.append(f"short_rfcomm_frame_at_{pos}")
            break
        address, control = data[pos], data[pos + 1]
        pos += 2
        dlci = address >> 2
        first_len = data[pos]
        pos += 1
        if first_len & 1:
            info_len = first_len >> 1
        else:
            if pos >= len(data):
                errors.append(f"missing_second_length_octet_at_{pos}")
                break
            info_len = (first_len >> 1) | (data[pos] << 7)
            pos += 1
        normalized = control & 0xEF
        frame_type = {0x2F: "SABM", 0x63: "UA", 0x0F: "DM", 0x43: "DISC", 0xEF: "UIH"}.get(normalized, f"CTRL_0x{normalized:02x}")
        if frame_type == "UIH" and dlci != 0 and (control & 0x10):
            if pos >= len(data):
                errors.append(f"missing_credit_octet_at_{pos}")
                break
            pos += 1
        # Every RFCOMM frame has one trailing FCS octet.
        if pos + info_len + 1 > len(data):
            errors.append(f"truncated_rfcomm_information_at_{frame_start}")
            break
        info = data[pos:pos + info_len]
        pos += info_len
        pos += 1  # FCS
        frames.append(RfcommFrame(pdu.timestamp, pdu.direction, pdu.handle, pdu.cid, dlci, frame_type, info_len, info.hex()))
    return frames, errors


def analyze_btsnoop_member(
    name: str,
    data: bytes,
    interval_start: dt.datetime,
    interval_end: dt.datetime,
    target_dlci: int,
    expected_lifecycle_start: Optional[dt.datetime] = None,
    expected_lifecycle_end: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    try:
        datalink, records, parse_errors = parse_btsnoop(data)
    except Exception as exc:
        return {"member": name, "member_sha256": hashlib.sha256(data).hexdigest(), "qualifies": False, "errors": [f"parse_error:{exc}"]}
    window_records = [r for r in records if interval_start - dt.timedelta(seconds=5) <= r.timestamp <= interval_end + dt.timedelta(seconds=5)]
    pdus, reassembly_errors = reassemble_l2cap(datalink, window_records)
    cids = discover_rfcomm_cids(pdus)
    frames: List[RfcommFrame] = []
    rfcomm_parse_errors: List[str] = []
    for pdu in pdus:
        if pdu.cid in cids.get(pdu.handle, set()):
            parsed_frames, frame_errors = parse_rfcomm_frames(pdu)
            frames.extend(parsed_frames)
            rfcomm_parse_errors.extend(f"pdu_{pdu.source_record_index}:{e}" for e in frame_errors)
    target = [f for f in frames if f.dlci == target_dlci]
    target.sort(key=lambda f: f.timestamp)
    sabm_frames = [f for f in target if f.frame_type == "SABM"]
    disc_frames = [f for f in target if f.frame_type == "DISC"]
    sabm = sabm_frames[0] if len(sabm_frames) == 1 else None
    ua_after_sabm = next((f for f in target if f.frame_type == "UA" and sabm and f.timestamp >= sabm.timestamp), None)
    disc = disc_frames[0] if len(disc_frames) == 1 and ua_after_sabm and disc_frames[0].timestamp >= ua_after_sabm.timestamp else None
    ua_after_disc = next((f for f in target if f.frame_type == "UA" and disc and f.timestamp >= disc.timestamp), None)
    lifecycle_complete = all([sabm, ua_after_sabm, disc, ua_after_disc]) and len(sabm_frames) == 1 and len(disc_frames) == 1
    active_frames = [f for f in target if sabm and ua_after_disc and sabm.timestamp <= f.timestamp <= ua_after_disc.timestamp]
    payload = [f for f in active_frames if f.frame_type == "UIH" and f.information_length > 0]
    tx_bytes = sum(f.information_length for f in payload if f.direction == "tx")
    rx_bytes = sum(f.information_length for f in payload if f.direction == "rx")
    drops = max((r.drops for r in window_records), default=0)
    truncations = sum(1 for r in window_records if r.included_length != r.original_length)
    first_ts = min((r.timestamp for r in window_records), default=None)
    last_ts = max((r.timestamp for r in window_records), default=None)
    coverage = bool(first_ts and last_ts and first_ts <= interval_start and last_ts >= interval_end)
    temporal_correlation = bool(
        lifecycle_complete
        and expected_lifecycle_start
        and expected_lifecycle_end
        and sabm.timestamp >= expected_lifecycle_start - dt.timedelta(seconds=5)
        and ua_after_disc.timestamp <= expected_lifecycle_end + dt.timedelta(seconds=5)
    ) if expected_lifecycle_start and expected_lifecycle_end else lifecycle_complete
    unique_handles = sorted({f.handle for f in target})
    complete_and_lossless = (
        lifecycle_complete and temporal_correlation and drops == 0 and truncations == 0
        and not parse_errors and not reassembly_errors and not rfcomm_parse_errors
        and coverage and len(unique_handles) == 1
    )
    frame_fingerprint = hashlib.sha256(json.dumps([
        [iso_utc(f.timestamp), f.direction, f.handle, f.cid, f.dlci, f.frame_type, f.information_length, f.payload_hex]
        for f in target
    ], separators=(",", ":")).encode()).hexdigest()
    return {
        "member": name,
        "member_sha256": hashlib.sha256(data).hexdigest(),
        "frame_fingerprint_sha256": frame_fingerprint,
        "datalink": datalink,
        "record_count": len(records),
        "window_record_count": len(window_records),
        "first_window_timestamp_utc": iso_utc(first_ts) if first_ts else None,
        "last_window_timestamp_utc": iso_utc(last_ts) if last_ts else None,
        "coverage": coverage,
        "temporal_correlation": temporal_correlation,
        "drops": drops,
        "truncated_record_count": truncations,
        "parse_errors": parse_errors,
        "reassembly_errors": reassembly_errors,
        "rfcomm_parse_errors": rfcomm_parse_errors,
        "rfcomm_cids": {str(k): sorted(v) for k, v in cids.items()},
        "target_dlci": target_dlci,
        "target_handle_candidates": unique_handles,
        "sabm_count": len(sabm_frames),
        "disc_count": len(disc_frames),
        "lifecycle_complete": lifecycle_complete,
        "sabm_utc": iso_utc(sabm.timestamp) if sabm else None,
        "ua_open_utc": iso_utc(ua_after_sabm.timestamp) if ua_after_sabm else None,
        "disc_utc": iso_utc(disc.timestamp) if disc else None,
        "ua_close_utc": iso_utc(ua_after_disc.timestamp) if ua_after_disc else None,
        "target_frame_count": len(target),
        "active_target_frame_count": len(active_frames),
        "payload_frame_count": len(payload),
        "tx_payload_frame_count": sum(1 for f in payload if f.direction == "tx"),
        "rx_payload_frame_count": sum(1 for f in payload if f.direction == "rx"),
        "tx_payload_bytes": tx_bytes,
        "rx_payload_bytes": rx_bytes,
        "zero_payload_proven": complete_and_lossless and tx_bytes == 0 and rx_bytes == 0 and len(payload) == 0,
        "positive_payload_observed": tx_bytes > 0 or rx_bytes > 0,
        "qualifies": complete_and_lossless,
        "frames": [dataclasses.asdict(f) | {"timestamp": iso_utc(f.timestamp)} for f in target],
    }

def iter_bugreport_btsnoop(capture_dir: Path) -> Iterator[Tuple[str, bytes]]:
    for zip_path in sorted(capture_dir.rglob("*.zip")):
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for info in zf.infolist():
                    lower = info.filename.lower()
                    if "btsnoop" in lower and not info.is_dir() and info.file_size >= 16:
                        yield f"{zip_path.relative_to(capture_dir).as_posix()}!/{info.filename}", zf.read(info)
        except zipfile.BadZipFile:
            continue
    for path in sorted(capture_dir.rglob("*btsnoop*")):
        if path.is_file() and path.suffix.lower() not in {".zip", ".txt", ".json"}:
            yield path.relative_to(capture_dir).as_posix(), path.read_bytes()


def redact_endpoint(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    parts = value.split(":")
    return "xx:xx:xx:xx:" + ":".join(parts[-2:]).lower() if len(parts) == 6 else "REDACTED"


def build_markdown(public: Dict[str, Any]) -> str:
    gates = public["gates"]
    hci = public.get("selected_hci_census") or {}
    return f"""# {RELEASE} instrumented RFCOMM zero-payload qualification

## Outcome

- Acceptance: **{public['acceptance']}**
- Qualification outcome: **{public['qualification_outcome']}**
- Client-side RFCOMM lifecycle: **{'PROVEN' if gates['lifecycle_closure_proven'] else 'NOT PROVEN'}**
- Frame-level explicit zero payload: **{'PROVEN' if gates['hci_zero_payload_proven'] else 'NOT PROVEN'}**
- Positive RFCOMM payload observed: **{'YES' if gates['positive_payload_observed'] else 'NO'}**

## Same-attempt tuple

| Field | Value |
|---|---:|
| Probe UID/PID | {public['tuple'].get('uid', 'UNRESOLVED')} / {public['tuple'].get('pid', 'UNRESOLVED')} |
| Slot | {public['tuple'].get('slot', 'UNRESOLVED')} |
| Port handle | {public['tuple'].get('port_handle', 'UNRESOLVED')} |
| SCN | {public['tuple'].get('scn', 'UNRESOLVED')} |
| DLCI | {public['tuple'].get('dlci', 'UNRESOLVED')} |
| MTU | {public['tuple'].get('mtu', 'UNRESOLVED')} |
| Endpoint | {public['tuple'].get('endpoint', 'UNRESOLVED')} |

## HCI RFCOMM census

| Gate | Value |
|---|---:|
| HCI member selected | {hci.get('member', 'NONE')} |
| Capture covers metadata interval | {hci.get('coverage', False)} |
| Loss/drop count | {hci.get('drops', 'UNRESOLVED')} |
| Truncated records | {hci.get('truncated_record_count', 'UNRESOLVED')} |
| DLCI lifecycle complete | {hci.get('lifecycle_complete', False)} |
| TX payload frames / bytes | {hci.get('tx_payload_frame_count', 'UNRESOLVED')} / {hci.get('tx_payload_bytes', 'UNRESOLVED')} |
| RX payload frames / bytes | {hci.get('rx_payload_frame_count', 'UNRESOLVED')} / {hci.get('rx_payload_bytes', 'UNRESOLVED')} |

## Interpretation

Full closure requires one client-side logcat lifecycle and one complete, lossless
HCI RFCOMM lifecycle for the same metadata interval. Only non-control UIH
information bytes on the target DLCI count as application payload. Logcat silence,
configuration zeros, and missing callbacks are corroboration only.
"""


def load_metadata(capture_dir: Path) -> Dict[str, Any]:
    path = capture_dir / "metadata.json"
    if not path.is_file():
        raise RuntimeError(f"missing capture metadata: {path}")
    metadata = json.loads(path.read_text(encoding="utf-8"))
    for key in ("interval_start_utc", "interval_end_utc", "phone_serial_sha256"):
        if key not in metadata:
            raise RuntimeError(f"metadata missing {key}")
    return metadata


def analyze(capture_dir: Path, output_dir: Path) -> Dict[str, Any]:
    metadata = load_metadata(capture_dir)
    start, end = parse_iso(metadata["interval_start_utc"]), parse_iso(metadata["interval_end_utc"])
    if end <= start:
        raise RuntimeError("invalid metadata interval")
    logcat = capture_dir / "logcat-all-epoch.txt"
    if not logcat.is_file():
        raise RuntimeError("missing logcat-all-epoch.txt")
    records = parse_logcat(logcat, start, end)
    lifecycle = reconstruct_lifecycle(records)
    target_dlci = int(lifecycle.get("fields", {}).get("dlci", metadata.get("expected_dlci", 6)))
    lifecycle_start = parse_iso(lifecycle["start_utc"]) if lifecycle.get("start_utc") else None
    lifecycle_end = parse_iso(lifecycle["end_utc"]) if lifecycle.get("end_utc") else None
    unique_members: Dict[str, Tuple[str, bytes, List[str]]] = {}
    for name, data in iter_bugreport_btsnoop(capture_dir):
        digest = hashlib.sha256(data).hexdigest()
        if digest in unique_members:
            unique_members[digest][2].append(name)
        else:
            unique_members[digest] = (name, data, [name])
    hci_members = []
    for _digest, (name, data, aliases) in unique_members.items():
        item = analyze_btsnoop_member(name, data, start, end, target_dlci, lifecycle_start, lifecycle_end)
        item["member_aliases"] = aliases
        hci_members.append(item)
    qualifying = [h for h in hci_members if h.get("qualifies")]
    qualifying_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in qualifying:
        qualifying_groups[item.get("frame_fingerprint_sha256", item["member_sha256"])].append(item)
    selected = None
    if len(qualifying_groups) == 1:
        selected = next(iter(qualifying_groups.values()))[0]
        selected["equivalent_qualifying_member_count"] = len(next(iter(qualifying_groups.values())))
    positive = any(h.get("positive_payload_observed") for h in hci_members)
    zero = bool(selected and selected.get("zero_payload_proven")) and not positive
    lifecycle_proven = bool(lifecycle.get("proven"))
    if lifecycle_proven and zero:
        acceptance = "PASS_FULL_RFCOMM_HCI_ZERO_PAYLOAD_CLOSURE"
        outcome = "RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS"
    elif lifecycle_proven and positive:
        acceptance = "FAIL_POSITIVE_RFCOMM_PAYLOAD_OBSERVED"
        outcome = "RFCOMM_CLIENT_RUNTIME_LIFECYCLE_PROVEN_POSITIVE_PAYLOAD_OBSERVED"
    elif lifecycle_proven:
        acceptance = "PASS_BOUNDED_RFCOMM_CLIENT_LIFECYCLE_CLOSURE_ONLY"
        outcome = "RFCOMM_CLIENT_RUNTIME_LIFECYCLE_CLOSURE_PROVEN_HCI_ZERO_PAYLOAD_NOT_PROVEN"
    else:
        acceptance = "FAIL_RFCOMM_CLIENT_LIFECYCLE_CLOSURE"
        outcome = "RFCOMM_CLIENT_RUNTIME_LIFECYCLE_CLOSURE_NOT_PROVEN"
    private = {
        "schema": SCHEMA_PRIVATE,
        "release": RELEASE,
        "acceptance": acceptance,
        "qualification_outcome": outcome,
        "metadata": metadata,
        "capture_tree_sha256": {p.relative_to(capture_dir).as_posix(): sha256_file(p) for p in sorted(capture_dir.rglob("*")) if p.is_file()},
        "logcat_record_count": len(records),
        "lifecycle": lifecycle,
        "hci_member_census": hci_members,
        "selected_hci_census": selected,
        "gates": {
            "lifecycle_closure_proven": lifecycle_proven,
            "hci_unique_qualifying_member": len(qualifying_groups) == 1,
            "hci_zero_payload_proven": zero,
            "positive_payload_observed": positive or lifecycle.get("positive_logcat_payload_event_count", 0) > 0,
            "full_zero_payload_closure_proven": lifecycle_proven and zero,
        },
    }
    fields = dict(lifecycle.get("fields", {}))
    if "endpoint" in fields:
        fields["endpoint"] = redact_endpoint(fields["endpoint"])
    public = {
        "schema": SCHEMA_PUBLIC,
        "release": RELEASE,
        "acceptance": acceptance,
        "qualification_outcome": outcome,
        "metadata_interval": {"start_utc": metadata["interval_start_utc"], "end_utc": metadata["interval_end_utc"]},
        "phone_serial_sha256": metadata["phone_serial_sha256"],
        "hci_preflight": {
            "status": metadata.get("hci_preflight", {}).get("status", "UNKNOWN"),
            "method": metadata.get("hci_preflight", {}).get("method", "UNKNOWN"),
            "post_bugreport_required": metadata.get("hci_preflight", {}).get("post_bugreport_required", True),
        },
        "tuple": fields,
        "gates": private["gates"],
        "selected_hci_census": None if selected is None else {k: v for k, v in selected.items() if k not in {"frames"}},
        "hci_member_count": len(hci_members),
        "qualifying_hci_member_count": len(qualifying),
        "qualifying_hci_stream_count": len(qualifying_groups),
        "offline_analysis": True,
    }
    analysis_dir = output_dir / "analysis"
    publication_dir = output_dir / "publication"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    publication_dir.mkdir(parents=True, exist_ok=True)
    write_json(analysis_dir / "r25.2.3.1-private-analysis.json", private)
    write_json(publication_dir / "r25.2.3.1-runtime-status-summary.json", public)
    (publication_dir / "r25.2.3.1-instrumented-rfcomm-hci-zero-payload.md").write_text(build_markdown(public), encoding="utf-8")
    (publication_dir / "methodology.md").write_text(
        "# Methodology\n\nThe host records an exact UTC interval, epoch logcat, Bluetooth diagnostics, and an Android bugreport. The offline analyzer reconstructs one client RFCOMM lifecycle, parses btsnoop HCI ACL/L2CAP/RFCOMM frames, identifies the RFCOMM L2CAP CIDs, and counts UIH information bytes on the target DLCI between SABM/UA and DISC/UA.\n",
        encoding="utf-8",
    )
    (publication_dir / "limitations.md").write_text(
        "# Limitations\n\nFull zero-payload promotion is unavailable when the HCI snoop log is absent, truncated, lossy, does not cover the interval, contains multiple qualifying DLCI lifecycles, or lacks explicit SABM/UA and DISC/UA boundaries. Logcat silence alone is not proof.\n",
        encoding="utf-8",
    )
    hashes = []
    for p in sorted(publication_dir.rglob("*")):
        if p.is_file() and p.name != "evidence-hashes.txt":
            hashes.append(f"{sha256_file(p)}  {p.relative_to(publication_dir).as_posix()}")
    (publication_dir / "evidence-hashes.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    return private


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = analyze(args.capture_dir.resolve(), args.output.resolve())
    gates = result["gates"]
    fields = result.get("lifecycle", {}).get("fields", {})
    selected = result.get("selected_hci_census") or {}
    print(f"R25_2_3_1_ATTEMPT_COUNT={1 if result.get('lifecycle', {}).get('start_utc') else 0}")
    print(f"R25_2_3_1_ANDROID_CLIENT_SEMANTIC={'YES' if result.get('lifecycle', {}).get('client_semantic') else 'NO'}")
    print(f"R25_2_3_1_RUNTIME_TUPLE={'YES' if result.get('lifecycle', {}).get('tuple_complete') else 'NO'}")
    print(f"R25_2_3_1_MATCHING_OPEN_CLOSE={'YES' if result.get('lifecycle', {}).get('matching_open_close') else 'NO'}")
    print(f"R25_2_3_1_HCI_MEMBER_COUNT={len(result.get('hci_member_census', []))}")
    print(f"R25_2_3_1_HCI_UNIQUE_QUALIFYING_MEMBER={'YES' if gates['hci_unique_qualifying_member'] else 'NO'}")
    print(f"R25_2_3_1_HCI_DLCI_LIFECYCLE={'YES' if selected.get('lifecycle_complete') else 'NO'}")
    print(f"R25_2_3_1_HCI_TX_PAYLOAD_BYTES={selected.get('tx_payload_bytes', 'UNRESOLVED')}")
    print(f"R25_2_3_1_HCI_RX_PAYLOAD_BYTES={selected.get('rx_payload_bytes', 'UNRESOLVED')}")
    print(f"R25_2_3_1_HCI_ZERO_PAYLOAD={'YES' if gates['hci_zero_payload_proven'] else 'NO'}")
    for key in ("uid", "pid", "slot", "port_handle", "scn", "dlci", "mtu"):
        print(f"R25_2_3_1_{key.upper()}={fields.get(key, 'UNRESOLVED')}")
    print(f"R25_2_3_1_QUALIFICATION_OUTCOME={result['qualification_outcome']}")
    print(f"R1_3_3_2_25_2_3_1_ACCEPTANCE={result['acceptance']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
