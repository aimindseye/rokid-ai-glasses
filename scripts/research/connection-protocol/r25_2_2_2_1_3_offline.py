#!/usr/bin/env python3
"""Offline r25.2.2.2.1.3 gate-projection and zero-payload census repair.

Consumes an existing private evidence ZIP only. It never imports subprocess or
network/device modules and never contacts the phone or glasses.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RELEASE = "r1.3.3.2.25.2.2.2.1.3"
SCHEMA_PRIVATE = "rokid.r25.2.2.2.1.3.private-analysis.v4"
SCHEMA_PUBLIC = "rokid.r25.2.2.2.1.3.public-gate-projection.v4"
SCHEMA_STATUS = "rokid.r25.2.runtime-status-summary.v2"
FULL_OUTCOME = "RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE"
LIFECYCLE_OUTCOME = "RFCOMM_CLIENT_RUNTIME_LIFECYCLE_CLOSURE_PROVEN_ZERO_PAYLOAD_NOT_PROVEN"
FAIL_OUTCOME = "RFCOMM_CLIENT_RUNTIME_LIFECYCLE_CLOSURE_NOT_PROVEN"
FULL_ACCEPTANCE = "PASS_FULL_ZERO_PAYLOAD_CLOSURE"
LIFECYCLE_ACCEPTANCE = "PASS_BOUNDED_RFCOMM_CLIENT_LIFECYCLE_CLOSURE_ONLY"
FAIL_ACCEPTANCE = "FAIL_RFCOMM_CLIENT_LIFECYCLE_CLOSURE"
PASS_ACCEPTANCE = FULL_ACCEPTANCE
EXPECTED_SOURCE_SHA256 = "35b209ab8243e68a26b3f32ab7f4bfcd111f88ece3d0be05c0a72e095dccf662"
EXPECTED = {
    "requested_service_uuid": "89679c22-9cac-464d-86d8-d254bc8b649b",
    "uid": 10320,
    "pid": 23810,
    "slot": 45,
    "port_handle": 29,
    "scn": 3,
    "dlci": 6,
    "mtu": 990,
}
TEXT_SUFFIXES = {".txt", ".log", ".json", ".jsonl", ".csv", ".xml", ".md", ".out"}
START_KEYS = ("metadata_start_utc", "attempt_start_utc", "action_start_utc", "capture_start_utc", "started_utc", "start_utc", "start_time_utc", "begin_utc")
END_KEYS = ("metadata_end_utc", "attempt_end_utc", "action_end_utc", "capture_end_utc", "finished_utc", "end_utc", "end_time_utc", "completed_utc", "stop_utc")

ISO_RE = re.compile(r"(?P<ts>20\d\d-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:?\d\d)?)")
THREADTIME_3_RE = re.compile(r"^\s*(?P<ts>\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d{3,9})\s+(?P<uid>\d+)\s+(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<priority>[VDIWEF])\s+(?P<body>.*)$")
THREADTIME_2_RE = re.compile(r"^\s*(?P<ts>\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d{3,9})\s+(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<priority>[VDIWEF])\s+(?P<body>.*)$")
EPOCH_RE = re.compile(r"^\s*(?P<ts>1\d{9}(?:\.\d{1,9})?|1\d{12})\s+(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<priority>[VDIWEF])\s+(?P<body>.*)$")
MAC_ANY_RE = re.compile(r"(?i)(?<![0-9a-fx])((?:[0-9a-f]{2}|xx)(?::(?:[0-9a-f]{2}|xx)){5})(?![0-9a-fx])")
RAW_MAC_RE = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{2}(?::[0-9a-f]{2}){5})(?![0-9a-f])")
UUID128_RE = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?![0-9a-f])")
NATIVE_UUID_RE = re.compile(r"(?i)\buuid\s*[=:]\s*(0x[0-9a-f]+)\b")

BT_SCOPE_RE = re.compile(
    r"(?i)(BluetoothSocketManagerBinder|BluetoothSocket\b|bt_btif_sock|btsock_|"
    r"rfcomm|rfc_port|rfc_mx|port_rfc|bta_jv|bt_port_api|cleanup_rfc_slot|"
    r"on_cli_rfc_connect|RFC_PORT_EVENT_|BTA_JV_RFCOMM_)"
)
PROBE_ZERO_SCOPE_RE = re.compile(r"(?i)(r25(?:[._ -]?2){2,}|channelprobe|connection-only|rfcomm|bluetooth|socket|probe|summary|status).*(payload|bytes|callbacks|read|write|data)|(?:payload|bytes|callbacks|read|write|data).*(rfcomm|connection-only|bluetooth|socket|probe|summary|status)")
DATA_EVENT_RE = re.compile(r"(?i)(BTA_JV_RFCOMM_DATA_IND_EVT|RFC_PORT_EVENT_RXCHAR|PORT_EV_RXCHAR|DATA_IND|data_received|onDataReceived|socket.*\bread\b|socket.*\bwrite\b)")

COUNTER_ALIASES = {
    "tx_bytes": ("tx_bytes", "bytes_written", "write_bytes", "written_bytes", "payload_tx_bytes", "sent_bytes", "bytes_sent", "tx_payload_bytes"),
    "rx_bytes": ("rx_bytes", "bytes_read", "read_bytes", "received_bytes", "payload_rx_bytes", "bytes_received", "rx_payload_bytes"),
    "payload_bytes": ("payload_bytes", "payload_len", "payload_length", "total_payload_bytes", "application_payload_bytes", "app_payload_bytes"),
    "data_callbacks": ("data_callbacks", "payload_callbacks", "rx_callbacks", "tx_callbacks", "data_event_count", "payload_event_count", "data_indications"),
}
CONFIG_ALIASES = (
    "max_rx_packet_size", "max_tx_packet_size", "buffer_size", "buffer_capacity",
    "queue_depth", "queue_capacity", "mtu", "initial_credits", "credit_count",
    "timeout", "socket_timeout", "endpoint_id", "hub_id", "data_path",
)

class AnalysisError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_text(data: bytes) -> Optional[str]:
    if b"\x00" in data[:4096]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def iter_archive_members(path: Path, max_depth: int = 2) -> Iterator[Tuple[str, bytes]]:
    data = path.read_bytes()
    def recurse(blob: bytes, prefix: str, depth: int) -> Iterator[Tuple[str, bytes]]:
        with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
            for info in sorted(zf.infolist(), key=lambda x: x.filename):
                if info.is_dir() or info.file_size > 128 * 1024 * 1024:
                    continue
                raw = zf.read(info)
                logical = f"{prefix}{info.filename}"
                suffix = Path(info.filename).suffix.lower()
                basename = Path(info.filename).name.lower()
                if suffix == ".zip" and depth < max_depth:
                    try:
                        yield from recurse(raw, logical + "!", depth + 1)
                    except zipfile.BadZipFile:
                        pass
                    continue
                if suffix in TEXT_SUFFIXES or any(token in basename for token in ("logcat", "bugreport", "metadata", "rfcomm", "bluetooth", "probe")):
                    yield logical, raw
    yield from recurse(data, "", 0)


def parse_datetime(value: Any) -> Optional[dt.datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000.0
        try:
            return dt.datetime.fromtimestamp(number, tz=dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{10}(?:\.\d+)?|\d{13}", text):
        return parse_datetime(float(text) if "." in text else int(text))
    normalized = text.replace(" ", "T", 1)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    if re.search(r"[+-]\d{4}$", normalized):
        normalized = normalized[:-5] + normalized[-5:-2] + ":" + normalized[-2:]
    try:
        result = dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=dt.timezone.utc)
    return result.astimezone(dt.timezone.utc)


def walk_json(obj: Any, prefix: str = "") -> Iterator[Tuple[str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, value
            yield from walk_json(value, path)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from walk_json(value, f"{prefix}[{i}]")


def discover_interval(path: Path) -> Tuple[dt.datetime, dt.datetime, Dict[str, str]]:
    candidates: List[Tuple[int, dt.datetime, dt.datetime, str, str]] = []
    for source, raw in iter_archive_members(path):
        if not any(token in source.lower() for token in ("metadata", "run-info", "handoff")):
            continue
        text = safe_text(raw)
        if text is None:
            continue
        pairs: List[Tuple[str, Any]] = []
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None
        if obj is not None:
            pairs = list(walk_json(obj))
        else:
            for line in text.splitlines():
                m = re.match(r"\s*([A-Za-z0-9_.-]+)\s*[=:]\s*(.*?)\s*$", line)
                if m:
                    pairs.append((m.group(1), m.group(2)))
        starts: List[Tuple[int, str, dt.datetime]] = []
        ends: List[Tuple[int, str, dt.datetime]] = []
        for key_path, value in pairs:
            key = key_path.rsplit(".", 1)[-1].lower()
            for priority, candidate in enumerate(START_KEYS):
                if key == candidate:
                    parsed = parse_datetime(value)
                    if parsed:
                        starts.append((priority, key_path, parsed))
            for priority, candidate in enumerate(END_KEYS):
                if key == candidate:
                    parsed = parse_datetime(value)
                    if parsed:
                        ends.append((priority, key_path, parsed))
        starts.sort(); ends.sort()
        for _, sp, start in starts:
            for _, ep, end in ends:
                if start <= end:
                    score = -100 if Path(source.split("!", 1)[0]).name.lower() == "run-metadata-private.json" else 0
                    if "r25.2.2.2" in source.lower():
                        score -= 20
                    candidates.append((score, start, end, f"{source}:{sp}", f"{source}:{ep}"))
                    break
            if candidates and candidates[-1][1] == start:
                break
    if not candidates:
        raise AnalysisError("No exact metadata start/end interval found")
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    _, start, end, ss, es = candidates[0]
    if end - start > dt.timedelta(hours=2):
        raise AnalysisError("Metadata interval exceeds two-hour bound")
    return start, end, {"start_source": ss, "end_source": es}


@dataclass(frozen=True)
class Timebase:
    offset_minutes: Optional[int]
    method: str
    confidence: str
    sources: Tuple[str, ...] = ()
    timezone_name: Optional[str] = None
    matched_pair_count: int = 0
    def as_dict(self) -> Dict[str, Any]:
        return {
            "threadtime_utc_offset_minutes": self.offset_minutes,
            "method": self.method,
            "confidence": self.confidence,
            "sources": list(self.sources),
            "timezone_name": self.timezone_name,
            "matched_pair_count": self.matched_pair_count,
            "semantic_maximization_used": False,
        }


def timezone_offset_minutes(name: str, instant: dt.datetime) -> Optional[int]:
    try:
        zone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    offset = instant.astimezone(zone).utcoffset()
    return int(offset.total_seconds() // 60) if offset is not None else None


def strip_prefix(line: str) -> Tuple[str, Dict[str, int], Optional[str], Optional[str]]:
    for kind, pattern in (("threadtime_uid_pid_tid", THREADTIME_3_RE), ("threadtime_pid_tid", THREADTIME_2_RE), ("unix_epoch", EPOCH_RE)):
        m = pattern.match(line)
        if m:
            context = {k: int(m.group(k)) for k in ("uid", "pid", "tid") if k in m.groupdict() and m.group(k)}
            return m.group("body").strip(), context, kind, m.group("ts")
    return re.sub(r"\s+", " ", line.strip()), {}, None, None


def metadata_timebases(path: Path, midpoint: dt.datetime) -> List[Timebase]:
    results: List[Timebase] = []
    for source, raw in iter_archive_members(path):
        if not any(t in source.lower() for t in ("metadata", "run-info", "handoff", "getprop", "bugreport")):
            continue
        text = safe_text(raw)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            m = re.search(r"(?:\[?persist\.sys\.timezone\]?\s*[:=]\s*\[?|\bTimezone\s*[:=]\s*)([A-Za-z_]+/[A-Za-z0-9_+\-]+)", line, re.I)
            if m:
                name = m.group(1).rstrip("]")
                offset = timezone_offset_minutes(name, midpoint)
                if offset is not None:
                    results.append(Timebase(offset, "bugreport_timezone_property", "explicit", (f"{source}:{number}",), name))
            m = re.search(r"\b(?:threadtime_utc_offset_minutes|phone_utc_offset_minutes|device_utc_offset_minutes|timezone_offset_minutes|utc_offset_minutes)\s*[:=]\s*([+-]?\d{1,4})\b", line, re.I)
            if m and -840 <= int(m.group(1)) <= 840:
                results.append(Timebase(int(m.group(1)), "metadata_text_offset", "explicit", (f"{source}:{number}",)))
    return results


def body_for_pairing(line: str) -> str:
    body, _, _, _ = strip_prefix(line)
    return re.sub(r"\s+", " ", body)


def paired_timebase(path: Path, year: int) -> Optional[Timebase]:
    epochs: Dict[str, List[Tuple[dt.datetime, str]]] = defaultdict(list)
    locals_: Dict[str, List[Tuple[dt.datetime, str]]] = defaultdict(list)
    for source, raw in iter_archive_members(path):
        text = safe_text(raw)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            body, _, kind, ts = strip_prefix(line)
            if not kind or not BT_SCOPE_RE.search(body):
                continue
            key = re.sub(r"\s+", " ", body)
            if kind == "unix_epoch":
                parsed = parse_datetime(float(ts) if "." in str(ts) else int(ts or 0))
                if parsed:
                    epochs[key].append((parsed, f"{source}:{number}"))
            elif kind.startswith("threadtime"):
                try:
                    local = dt.datetime.strptime(f"{year}-{ts}", "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    continue
                locals_[key].append((local, f"{source}:{number}"))
    votes: Counter[int] = Counter(); sources: Dict[int, List[str]] = defaultdict(list)
    for key in set(epochs) & set(locals_):
        for epoch, es in epochs[key][:2]:
            for local, ls in locals_[key][:2]:
                minutes = (local - epoch.astimezone(dt.timezone.utc).replace(tzinfo=None)).total_seconds() / 60
                rounded = int(round(minutes / 15) * 15)
                if -840 <= rounded <= 840 and abs(minutes - rounded) * 60 <= 2:
                    votes[rounded] += 1; sources[rounded].extend([es, ls]); break
            else:
                continue
            break
    if not votes:
        return None
    ordered = votes.most_common()
    offset, count = ordered[0]
    if count < 2 or (len(ordered) > 1 and ordered[1][1] == count):
        return None
    return Timebase(offset, "paired_epoch_threadtime_records", "explicit_cross_format_correlation", tuple(dict.fromkeys(sources[offset])), matched_pair_count=count)


def resolve_timebase(path: Path, start: dt.datetime, end: dt.datetime) -> Timebase:
    candidates = metadata_timebases(path, start + (end - start) / 2)
    paired = paired_timebase(path, start.year)
    if paired:
        candidates.append(paired)
    if candidates:
        offsets = {c.offset_minutes for c in candidates}
        if len(offsets) != 1:
            raise AnalysisError("Conflicting explicit threadtime timebases: " + ", ".join(f"{c.method}={c.offset_minutes}" for c in candidates))
        preferred = sorted(candidates, key=lambda c: (0 if "metadata" in c.method or "bugreport" in c.method else 1, -c.matched_pair_count))[0]
        return Timebase(preferred.offset_minutes, "+".join(sorted({c.method for c in candidates})), "explicit_correlated" if len(candidates) > 1 else preferred.confidence, tuple(dict.fromkeys(s for c in candidates for s in c.sources)), next((c.timezone_name for c in candidates if c.timezone_name), None), max(c.matched_pair_count for c in candidates))
    # Threadtime lines exist in this evidence; fail closed rather than guessing.
    for _, raw in iter_archive_members(path):
        text = safe_text(raw)
        if text and any((THREADTIME_3_RE.match(line) or THREADTIME_2_RE.match(line)) and BT_SCOPE_RE.search(strip_prefix(line)[0]) for line in text.splitlines()):
            raise AnalysisError("Bluetooth threadtime records present without explicit timebase provenance")
    return Timebase(None, "threadtime_not_required", "not_applicable")


def parse_timestamp(line: str, year: int, timebase: Timebase) -> Tuple[Optional[dt.datetime], str, str, Dict[str, int], str]:
    m = ISO_RE.search(line)
    if m:
        parsed = parse_datetime(m.group("ts"))
        return parsed, "iso8601", "embedded_utc_or_offset", {}, strip_prefix(line)[0]
    body, context, kind, ts = strip_prefix(line)
    if kind == "unix_epoch":
        parsed = parse_datetime(float(ts) if "." in str(ts) else int(ts or 0))
        return parsed, kind, "epoch_is_utc", context, body
    if kind and kind.startswith("threadtime"):
        if timebase.offset_minutes is None:
            return None, kind, "unresolved", context, body
        try:
            naive = dt.datetime.strptime(f"{year}-{ts}", "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return None, kind, "invalid", context, body
        parsed = naive.replace(tzinfo=dt.timezone.utc) - dt.timedelta(minutes=timebase.offset_minutes)
        return parsed, kind, timebase.method, context, body
    return None, "none", "none", context, body


def parse_int(text: str, names: Sequence[str]) -> Optional[int]:
    for name in names:
        m = re.search(rf"(?i)\b{re.escape(name)}\s*[=:]\s*((?:0x)?[0-9a-f]+)\b", text)
        if m:
            try:
                return int(m.group(1), 0)
            except ValueError:
                pass
    return None


def endpoint_parts(value: str) -> Optional[List[str]]:
    parts = value.lower().split(":")
    return parts if len(parts) == 6 and all(p == "xx" or re.fullmatch(r"[0-9a-f]{2}", p) for p in parts) else None


def endpoint_compatible(values: Sequence[str]) -> bool:
    parsed = [endpoint_parts(v) for v in values]
    parsed = [p for p in parsed if p]
    if not parsed:
        return False
    for column in zip(*parsed):
        concrete = {v for v in column if v != "xx"}
        if len(concrete) > 1:
            return False
    return True


def preferred_endpoint(values: Sequence[str]) -> str:
    return max(values, key=lambda v: sum(p != "xx" for p in (endpoint_parts(v) or []))).upper()


def classify_event(body: str) -> str:
    lower = body.lower()
    # Explicit close tokens have precedence over function names such as rfc_port_sm_opened.
    if "rfc_port_event_close" in lower:
        return "port_close_event"
    if "cleanup_rfc_slot" in lower and ("disconnected" in lower or "close" in lower):
        return "slot_cleanup"
    if "port_rfc_closed" in lower or "bta_jv_rfcomm_close_evt" in lower or "btajvrfcommclose" in lower:
        return "native_close"
    if "connectsocket:" in lower and "bluetoothsocketmanagerbinder" in lower:
        return "connect_request"
    if "btsock_rfc_connect" in lower:
        return "rfcomm_socket_request"
    if "rfcomm_createconnectionwithsecurity" in lower:
        return "native_create_client" if re.search(r"(?i)\bis_server\s*[=:]\s*(?:false|0)\b", body) else "native_create"
    if "rfc_port_event_open" in lower:
        return "port_open_event"
    if "bta_jv_rfcomm_open_evt" in lower:
        return "jv_open_event"
    if "on_cli_rfc_connect" in lower:
        return "client_connected"
    if "bluetoothsocket" in lower and "socket connected" in lower:
        return "socket_connected"
    if DATA_EVENT_RE.search(body):
        return "payload_data_event"
    return "rfcomm_state"


def extract_fields(body: str, context: Dict[str, int], event_type: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    if not (BT_SCOPE_RE.search(body) or PROBE_ZERO_SCOPE_RE.search(body)):
        return fields
    m = MAC_ANY_RE.search(body)
    if m and re.search(r"(?i)(device|bd_addr|address|addr|peer|remote|endpoint|RFCOMM peer)\s*[=:]", body):
        fields["endpoint"] = m.group(1).upper()
    if event_type in {"connect_request", "rfcomm_socket_request"}:
        m = re.search(r"(?i)\b(?:service_uuid|uuid)\s*[=:]\s*([0-9a-f-]{36})\b", body)
        if m:
            fields["requested_service_uuid"] = m.group(1).lower()
    if event_type in {"native_create_client", "native_create", "native_close"}:
        m = NATIVE_UUID_RE.search(body)
        if m:
            fields["native_service_class_uuid"] = m.group(1).lower()
    pair = re.search(r"(?i)\bfrom\s+uid/pid\s*[=:]\s*(\d+)\s*/\s*(\d+)\b", body)
    if pair:
        fields["uid"] = int(pair.group(1)); fields["pid"] = int(pair.group(2))
    app_uid = parse_int(body, ("app_uid", "probe_uid"))
    if app_uid is not None:
        fields["uid"] = app_uid % 100000 if app_uid >= 100000 else app_uid
    probe_pid = parse_int(body, ("probe_pid",))
    if probe_pid is not None:
        fields["pid"] = probe_pid
    if event_type == "socket_connected" and "uid" in context and "pid" in context:
        fields.setdefault("uid", context["uid"] % 100000 if context["uid"] >= 100000 else context["uid"])
        fields.setdefault("pid", context["pid"])
    fields["source_pid"] = context["pid"] if "pid" in context else None
    slot = parse_int(body, ("slot_id", "rfcomm_slot_id"))
    if slot is None and event_type == "client_connected":
        slot = parse_int(body, ("id",))
    if slot is not None:
        fields["slot"] = slot
    for key, aliases in {
        "port_handle": ("port_handle",), "scn": ("scn", "server_channel"),
        "dlci": ("dlci",), "mtu": ("mtu",), "socket_id": ("socket_id",),
    }.items():
        value = parse_int(body, aliases)
        if value is not None:
            fields[key] = value
    for canonical, aliases in COUNTER_ALIASES.items():
        value = parse_int(body, aliases)
        if value is not None:
            fields[canonical] = value
    if re.search(r"(?i)\bzero[_ -]?payload\s*[=:]\s*(?:true|yes|1)\b", body):
        fields["zero_payload_explicit"] = True
    return {k: v for k, v in fields.items() if v is not None}


def client_semantic(event_type: str, body: str) -> bool:
    return event_type in {"connect_request", "rfcomm_socket_request", "native_create_client", "client_connected", "socket_connected"} or bool(re.search(r"(?i)\bis_server\s*[=:]\s*(?:false|0)\b", body))


def canonical_body(body: str) -> str:
    result = body.strip()
    result = re.sub(r"(?i)\b(?:system/)?(?:btif|stack|bta)/[^\s:]+:\d+\s+", "", result)
    result = re.sub(r"\s+", " ", result)
    return result


@dataclass
class EvidenceRecord:
    timestamp: dt.datetime
    event_type: str
    body: str
    fields: Dict[str, Any]
    client: bool
    sources: List[Dict[str, Any]] = field(default_factory=list)
    fingerprint: str = ""
    def merge(self, other: "EvidenceRecord") -> None:
        for key, value in other.fields.items():
            if key not in self.fields or key == "source_pid":
                self.fields[key] = value
        for source in other.sources:
            if source not in self.sources:
                self.sources.append(source)
        self.client = self.client or other.client


def event_fingerprint(timestamp: dt.datetime, event_type: str, body: str) -> str:
    payload = {"timestamp_ms": int(round(timestamp.timestamp() * 1000)), "event_type": event_type, "body": canonical_body(body)}
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def collect_records(path: Path, start: dt.datetime, end: dt.datetime) -> Tuple[List[EvidenceRecord], Dict[str, Any], Timebase]:
    timebase = resolve_timebase(path, start, end)
    stats: Dict[str, Any] = {"raw_timestamped_lines": 0, "outside_interval_lines": 0, "inside_interval_lines": 0, "bluetooth_scoped_lines": 0, "duplicate_semantic_lines": 0, "ignored_unscoped_lines": 0, "timestamp_kind_counts": {}, "source_class_counts": {}}
    kinds: Counter[str] = Counter(); classes: Counter[str] = Counter(); seen: Dict[str, EvidenceRecord] = {}
    for source, raw in iter_archive_members(path):
        text = safe_text(raw)
        if text is None:
            continue
        source_class = "bugreport" if "bugreport" in source.lower() else "logcat" if "logcat" in source.lower() else "other"
        for number, line in enumerate(text.splitlines(), 1):
            timestamp, kind, tb_source, context, body = parse_timestamp(line, start.year, timebase)
            if timestamp is None:
                continue
            stats["raw_timestamped_lines"] += 1; kinds[kind] += 1; classes[source_class] += 1
            if not (start <= timestamp <= end):
                stats["outside_interval_lines"] += 1; continue
            stats["inside_interval_lines"] += 1
            if not BT_SCOPE_RE.search(body):
                stats["ignored_unscoped_lines"] += 1; continue
            event_type = classify_event(body)
            fields = extract_fields(body, context, event_type)
            if event_type == "rfcomm_state" and not fields:
                # State-only lines are retained only when they contain an endpoint or handle.
                continue
            stats["bluetooth_scoped_lines"] += 1
            record = EvidenceRecord(timestamp, event_type, canonical_body(body), fields, client_semantic(event_type, body), [{"source": source, "line": number, "timestamp_kind": kind, "timebase_source": tb_source, "raw_text": line}])
            record.fingerprint = event_fingerprint(timestamp, event_type, body)
            if record.fingerprint in seen:
                seen[record.fingerprint].merge(record); stats["duplicate_semantic_lines"] += 1
            else:
                seen[record.fingerprint] = record
    records = sorted(seen.values(), key=lambda r: (r.timestamp, r.event_type, r.fingerprint))
    stats["timestamp_kind_counts"] = dict(sorted(kinds.items())); stats["source_class_counts"] = dict(sorted(classes.items())); stats["timebase_provenance"] = timebase.as_dict()
    return records, stats, timebase


@dataclass
class ZeroCandidate:
    fingerprint: str
    counters: Dict[str, int]
    assertions: Dict[str, bool]
    identity_fields: Dict[str, Any]
    timestamp: Optional[dt.datetime]
    raw_text: str
    scope_tags: List[str]
    configuration_fields: Dict[str, int]
    sources: List[Dict[str, Any]] = field(default_factory=list)
    verdict: str = "unclassified"
    reasons: List[str] = field(default_factory=list)
    correlated_attempt_ids: List[str] = field(default_factory=list)

    def proof_capable(self) -> bool:
        explicit = self.assertions.get("zero_payload", False) or self.assertions.get("no_payload_observed", False)
        bidirectional = self.counters.get("tx_bytes") == 0 and self.counters.get("rx_bytes") == 0
        aggregate = self.counters.get("payload_bytes") == 0
        return explicit or bidirectional or aggregate

    def contradicts_zero(self) -> bool:
        return any(value > 0 for value in self.counters.values()) or self.assertions.get("payload_observed", False)

    def corroborates_zero(self) -> bool:
        return bool(self.counters) and all(value == 0 for value in self.counters.values())


def zero_identity_from_mapping(lowered: Dict[str, Any]) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for key in ("requested_service_uuid", "service_uuid", "rfcomm_uuid"):
        if key in lowered:
            match = UUID128_RE.search(str(lowered[key]))
            if match:
                fields["requested_service_uuid"] = match.group(1).lower()
                break
    aliases = {
        "uid": ("probe_uid", "app_uid", "requestor_uid", "uid"),
        "pid": ("probe_pid", "requestor_pid", "pid"),
        "slot": ("slot", "slot_id", "rfcomm_slot_id"),
        "port_handle": ("port_handle",),
        "scn": ("scn", "server_channel"),
        "dlci": ("dlci",),
        "mtu": ("mtu",),
        "socket_id": ("socket_id",),
    }
    for canonical, names in aliases.items():
        for name in names:
            if name not in lowered:
                continue
            try:
                fields[canonical] = int(str(lowered[name]), 0)
            except (TypeError, ValueError):
                pass
            break
    for key in ("endpoint", "device", "bd_addr", "address"):
        if key in lowered:
            match = MAC_ANY_RE.search(str(lowered[key]))
            if match:
                fields["endpoint"] = normalize_endpoint(match.group(1))
                break
    return fields


def zero_identity_from_text(text: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    uuid_match = re.search(r"(?i)\b(?:requested_service_uuid|service_uuid|rfcomm_uuid)\s*[=:]\s*([0-9a-f-]{36})", text)
    if uuid_match and UUID128_RE.fullmatch(uuid_match.group(1)):
        fields["requested_service_uuid"] = uuid_match.group(1).lower()
    aliases = {
        "uid": ("probe_uid", "app_uid", "requestor_uid"),
        "pid": ("probe_pid", "requestor_pid"),
        "slot": ("slot", "slot_id", "rfcomm_slot_id"),
        "port_handle": ("port_handle",),
        "scn": ("scn", "server_channel"),
        "dlci": ("dlci",),
        "mtu": ("mtu",),
        "socket_id": ("socket_id",),
    }
    for canonical, names in aliases.items():
        value = parse_int(text, names)
        if value is not None:
            fields[canonical] = value
    match = MAC_ANY_RE.search(text)
    if match:
        fields["endpoint"] = normalize_endpoint(match.group(1))
    return fields


def zero_timestamp_from_mapping(lowered: Dict[str, Any]) -> Optional[dt.datetime]:
    for key in ("timestamp_utc", "event_utc", "observed_utc", "finished_utc", "completed_utc", "attempt_end_utc", "attempt_start_utc"):
        if key in lowered:
            parsed = parse_datetime(lowered[key])
            if parsed is not None:
                return parsed
    return None


def candidate_scope_tags(source: str, text: str) -> List[str]:
    combined = source + " " + text
    tags: List[str] = []
    if BT_SCOPE_RE.search(combined): tags.append("bluetooth_rfcomm")
    if re.search(r"(?i)(r25(?:[._ -]?2){2,}|channelprobe|connection-only|probe)", combined): tags.append("probe")
    if re.search(r"(?i)(payload|bytes[_ -]?(?:read|written|sent|received)|tx_bytes|rx_bytes|data_callbacks|payload_event|zero[_ -]?payload|no payload|payload_observed|payload_transferred)", combined): tags.append("payload_semantic")
    if re.search(r"(?i)(summary|status|metrics|result|analysis|report)", source): tags.append("summary_member")
    return sorted(set(tags))


def extract_counter_mapping(lowered: Dict[str, Any]) -> Tuple[Dict[str, int], Dict[str, int]]:
    counters: Dict[str, int] = {}
    configs: Dict[str, int] = {}
    for canonical, aliases in COUNTER_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                try: counters[canonical] = int(str(lowered[alias]), 0)
                except (TypeError, ValueError): pass
                break
    for alias in CONFIG_ALIASES:
        if alias in lowered:
            try: configs[alias] = int(str(lowered[alias]), 0)
            except (TypeError, ValueError): pass
    return counters, configs


def extract_counter_text(text: str) -> Tuple[Dict[str, int], Dict[str, int]]:
    counters: Dict[str, int] = {}
    configs: Dict[str, int] = {}
    for canonical, aliases in COUNTER_ALIASES.items():
        value = parse_int(text, aliases)
        if value is not None: counters[canonical] = value
    for alias in CONFIG_ALIASES:
        value = parse_int(text, (alias,))
        if value is not None: configs[alias] = value
    return counters, configs


def assertions_from_mapping(lowered: Dict[str, Any]) -> Dict[str, bool]:
    result: Dict[str, bool] = {}
    def truthy(value: Any) -> bool: return value is True or str(value).strip().lower() in {"1","yes","true","pass"}
    def falsey(value: Any) -> bool: return value is False or str(value).strip().lower() in {"0","no","false","none"}
    for key in ("zero_payload", "zero_payload_confirmed", "payload_zero"):
        if key in lowered and truthy(lowered[key]): result["zero_payload"] = True
    for key in ("no_payload", "no_payload_observed", "no_data_observed"):
        if key in lowered and truthy(lowered[key]): result["no_payload_observed"] = True
    for key in ("payload_observed", "payload_transferred", "data_observed"):
        if key in lowered:
            if truthy(lowered[key]): result["payload_observed"] = True
            elif falsey(lowered[key]): result["no_payload_observed"] = True
    return result


def assertions_from_text(text: str) -> Dict[str, bool]:
    result: Dict[str, bool] = {}
    if re.search(r"(?i)\b(?:zero[_ -]?payload|payload[_ -]?zero)\s*[=:]\s*(?:true|yes|1|pass)\b", text): result["zero_payload"] = True
    if re.search(r"(?i)\b(?:no[_ -]?payload(?:[_ -]?observed)?|no application payload|no data observed)\s*(?:[=:]\s*(?:true|yes|1|pass))?\b", text): result["no_payload_observed"] = True
    if re.search(r"(?i)\b(?:payload[_ -]?(?:observed|transferred)|data[_ -]?observed)\s*[=:]\s*(?:true|yes|1)\b", text): result["payload_observed"] = True
    if re.search(r"(?i)\b(?:payload[_ -]?(?:observed|transferred)|data[_ -]?observed)\s*[=:]\s*(?:false|no|0)\b", text): result["no_payload_observed"] = True
    return result


def candidate_fingerprint(counters: Dict[str,int], assertions: Dict[str,bool], identity: Dict[str,Any], timestamp: Optional[dt.datetime], raw_text: str) -> str:
    payload = {"counters": counters, "assertions": assertions, "identity": identity, "timestamp_ms": int(round(timestamp.timestamp()*1000)) if timestamp else None, "body": canonical_body(raw_text)}
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def extract_zero_payload_candidates(path: Path, start: dt.datetime, end: dt.datetime, timebase: Timebase) -> Tuple[List[ZeroCandidate], Dict[str, Any]]:
    merged: Dict[str, ZeroCandidate] = {}
    member_count = 0
    line_count = 0
    raw_candidate_count = 0
    def add(source: str, location: str, raw_text: str, counters: Dict[str,int], assertions: Dict[str,bool], identity: Dict[str,Any], timestamp: Optional[dt.datetime], configs: Dict[str,int]) -> None:
        nonlocal raw_candidate_count
        tags = candidate_scope_tags(source, raw_text)
        if not counters and not assertions and not configs: return
        if not tags and not configs: return
        raw_candidate_count += 1
        fp = candidate_fingerprint(counters, assertions, identity, timestamp, raw_text)
        source_ref = {"source": source, "location": location}
        if fp in merged:
            if source_ref not in merged[fp].sources: merged[fp].sources.append(source_ref)
            return
        merged[fp] = ZeroCandidate(fp, counters, assertions, identity, timestamp, raw_text.strip(), tags, configs, [source_ref])
    for source, raw in iter_archive_members(path):
        member_count += 1
        text = safe_text(raw)
        if text is None: continue
        try: obj = json.loads(text)
        except json.JSONDecodeError: obj = None
        if obj is not None:
            def visit(value: Any, path_: str = "$") -> None:
                if isinstance(value, dict):
                    lowered = {str(k).lower(): v for k,v in value.items()}
                    counters, configs = extract_counter_mapping(lowered)
                    assertions = assertions_from_mapping(lowered)
                    scope_text = json.dumps(value, sort_keys=True)
                    add(source, path_, scope_text, counters, assertions, zero_identity_from_mapping(lowered), zero_timestamp_from_mapping(lowered), configs)
                    for key, child in value.items(): visit(child, f"{path_}.{key}")
                elif isinstance(value, list):
                    for index, child in enumerate(value): visit(child, f"{path_}[{index}]")
            visit(obj)
        for number, line in enumerate(text.splitlines(), 1):
            line_count += 1
            counters, configs = extract_counter_text(line)
            assertions = assertions_from_text(line)
            if not counters and not assertions and not configs: continue
            timestamp, _, body, _, _ = parse_timestamp(line, start.year, timebase)
            add(source, f"line:{number}", body or line, counters, assertions, zero_identity_from_text(body or line), timestamp, configs)
    candidates = sorted(merged.values(), key=lambda c: (c.timestamp or dt.datetime.min.replace(tzinfo=dt.timezone.utc), c.fingerprint))
    return candidates, {"members_scanned": member_count, "lines_scanned": line_count, "raw_candidates_found": raw_candidate_count, "deduplicated_candidates": len(candidates)}

def values_compatible(key: str, current: Any, candidate: Any) -> bool:
    if current is None or candidate is None:
        return True
    if key == "endpoint":
        return endpoint_compatible([str(current), str(candidate)])
    return current == candidate


@dataclass
class Attempt:
    attempt_id: str
    records: List[EvidenceRecord]
    zero_candidates: List[ZeroCandidate]
    fields: Dict[str, Any] = field(default_factory=dict)
    conflicts: Dict[str, List[Any]] = field(default_factory=dict)
    def aggregate(self) -> None:
        values: Dict[str, List[Any]] = defaultdict(list)
        for record in self.records:
            for key, value in record.fields.items():
                if key == "source_pid": continue
                if value not in values[key]: values[key].append(value)
        self.fields = {}; self.conflicts = {}
        for key, observed in values.items():
            if len(observed) == 1: self.fields[key] = observed[0]
            elif key == "endpoint" and endpoint_compatible([str(v) for v in observed]):
                self.fields[key] = preferred_endpoint([str(v) for v in observed]); self.fields["endpoint_alias_count"] = len(observed)
            else: self.conflicts[key] = observed
    def client_semantic(self) -> bool: return any(r.client for r in self.records)
    def open_records(self) -> List[EvidenceRecord]: return [r for r in self.records if r.event_type in {"port_open_event","jv_open_event","client_connected","socket_connected"}]
    def close_records(self) -> List[EvidenceRecord]: return [r for r in self.records if r.event_type in {"port_close_event","native_close"}]
    def lifecycle_pair(self) -> Optional[Tuple[EvidenceRecord, EvidenceRecord]]:
        for opened in self.open_records():
            for closed in self.close_records():
                if closed.timestamp <= opened.timestamp: continue
                oh,ch=opened.fields.get("port_handle"),closed.fields.get("port_handle")
                oe,ce=opened.fields.get("endpoint"),closed.fields.get("endpoint")
                if oh is not None and ch is not None and oh != ch: continue
                if oe and ce and not endpoint_compatible([str(oe),str(ce)]): continue
                if oh is not None or ch is not None or (oe and ce): return opened,closed
        return None
    def tuple_complete(self) -> bool: return all(key in self.fields for key in EXPECTED) and "endpoint" in self.fields
    def expected_match(self) -> bool: return all(self.fields.get(key) == value for key,value in EXPECTED.items())
    def conflict_free(self) -> bool: return not any(key in self.conflicts for key in ("requested_service_uuid","endpoint","uid","pid","slot","port_handle","scn","dlci","mtu"))
    def lifecycle_qualified(self) -> bool: return self.client_semantic() and self.tuple_complete() and self.expected_match() and self.conflict_free() and self.lifecycle_pair() is not None
    def zero_payload_result(self) -> Dict[str, Any]:
        data_events=[r for r in self.records if r.event_type=="payload_data_event"]
        correlated=[c for c in self.zero_candidates if c.verdict.startswith("accepted_") or c.verdict=="correlated_contradiction"]
        counters: Dict[str,List[int]]=defaultdict(list)
        explicit=False
        proof_fps=[]; corroborating_fps=[]; contradiction_fps=[]
        for item in correlated:
            explicit = explicit or item.assertions.get("zero_payload",False) or item.assertions.get("no_payload_observed",False)
            for key,value in item.counters.items(): counters[key].append(value)
            if item.verdict=="accepted_zero_proof_candidate": proof_fps.append(item.fingerprint)
            elif item.verdict=="accepted_zero_corroboration": corroborating_fps.append(item.fingerprint)
            elif item.verdict=="correlated_contradiction": contradiction_fps.append(item.fingerprint)
        positive={k:sorted(set(v for v in values if v>0)) for k,values in counters.items() if any(v>0 for v in values)}
        all_zero={k:sorted(set(values)) for k,values in counters.items() if values and all(v==0 for v in values)}
        bidirectional="tx_bytes" in all_zero and "rx_bytes" in all_zero
        aggregate="payload_bytes" in all_zero
        callbacks_zero="data_callbacks" in all_zero
        proven=not data_events and not positive and not contradiction_fps and bool(proof_fps) and (explicit or bidirectional or aggregate)
        return {"proven":proven,"explicit_zero":explicit,"bidirectional_zero":bidirectional,"aggregate_zero":aggregate,"callbacks_zero":callbacks_zero,"positive_counters":positive,"zero_counters":all_zero,"payload_data_event_count":len(data_events),"correlated_candidate_count":len(correlated),"proof_candidate_count":len(proof_fps),"corroborating_candidate_count":len(corroborating_fps),"contradiction_candidate_count":len(contradiction_fps),"proof_candidate_fingerprints":proof_fps,"corroborating_candidate_fingerprints":corroborating_fps,"contradiction_candidate_fingerprints":contradiction_fps}
    def gate_projection(self) -> Dict[str, bool]:
        zero=self.zero_payload_result()
        return {"client_semantic":self.client_semantic(),"tuple_complete":self.tuple_complete(),"expected_values_match":self.expected_match(),"conflict_free":self.conflict_free(),"matching_open_close":self.lifecycle_pair() is not None,"lifecycle_closure_proven":self.lifecycle_qualified(),"no_payload_data_event_observed":zero["payload_data_event_count"]==0,"no_positive_payload_counter_observed":not bool(zero["positive_counters"]) and zero["contradiction_candidate_count"]==0,"explicit_zero_payload_proven":zero["proven"],"full_zero_payload_closure_proven":self.lifecycle_qualified() and zero["proven"]}
    def accepted(self) -> bool: return self.gate_projection()["full_zero_payload_closure_proven"]

def compatible_with_seed(record: EvidenceRecord, fields: Dict[str, Any]) -> bool:
    for key in ("endpoint", "requested_service_uuid", "uid", "pid", "slot", "port_handle", "socket_id"):
        if key in fields and key in record.fields and not values_compatible(key, fields[key], record.fields[key]):
            return False
    return True


def group_attempts(records: Sequence[EvidenceRecord]) -> List[Attempt]:
    roots = [r for r in records if r.event_type in {"connect_request", "rfcomm_socket_request"}]
    # Coalesce same-timestamp compatible root records into one seed.
    seed_groups: List[List[EvidenceRecord]] = []
    for root in roots:
        placed = False
        for group in seed_groups:
            if abs((root.timestamp - group[0].timestamp).total_seconds()) <= 0.100:
                endpoints = [r.fields.get("endpoint") for r in group if r.fields.get("endpoint")]
                candidate = root.fields.get("endpoint")
                if not endpoints or not candidate or endpoint_compatible([*(str(v) for v in endpoints), str(candidate)]):
                    group.append(root); placed = True; break
        if not placed:
            seed_groups.append([root])
    if not seed_groups:
        seed_groups = [[r] for r in records if r.event_type == "native_create_client"]
    attempts: List[Attempt] = []
    for index, seed in enumerate(seed_groups):
        start = min(r.timestamp for r in seed)
        next_start = min((min(r.timestamp for r in other) for other in seed_groups if min(r.timestamp for r in other) > start), default=None)
        fields: Dict[str, Any] = {}
        selected: List[EvidenceRecord] = []
        for r in seed:
            selected.append(r)
            for key, value in r.fields.items():
                if key != "source_pid": fields.setdefault(key, value)
        close_seen = False
        for record in records:
            if record in selected or record.timestamp < start - dt.timedelta(milliseconds=5):
                continue
            if next_start is not None and record.timestamp >= next_start:
                break
            if record.timestamp > start + dt.timedelta(seconds=30):
                break
            if not compatible_with_seed(record, fields):
                continue
            # Unkeyed state lines may bridge the lifecycle only while the same RFCOMM attempt is active.
            selected.append(record)
            for key, value in record.fields.items():
                if key == "source_pid": continue
                if key not in fields:
                    fields[key] = value
                elif key == "endpoint" and values_compatible(key, fields[key], value):
                    fields[key] = preferred_endpoint([str(fields[key]), str(value)])
            if record.event_type in {"port_close_event", "native_close"}:
                close_seen = True
            if close_seen and record.timestamp > start + dt.timedelta(seconds=1) and record.event_type == "native_close":
                # Keep same-timestamp close records; later unrelated RFCOMM records are excluded.
                pass
        # Bound at final matching native close/port close plus 2 ms.
        close_times = [r.timestamp for r in selected if r.event_type in {"port_close_event", "native_close"}]
        if close_times:
            end = max(close_times) + dt.timedelta(milliseconds=2)
            selected = [r for r in selected if r.timestamp <= end]
        attempt = Attempt(f"lifecycle-{index + 1}", sorted(selected, key=lambda r: (r.timestamp, r.event_type)), [])
        attempt.aggregate(); attempts.append(attempt)
    return attempts


def correlate_zero_candidates(attempts: List[Attempt], candidates: List[ZeroCandidate], start: dt.datetime, end: dt.datetime) -> Dict[str, Any]:
    verdicts=Counter(); reasons=Counter()
    lifecycle_attempts=[a for a in attempts if a.lifecycle_qualified()]
    for item in candidates:
        item.reasons=[]; item.correlated_attempt_ids=[]
        if item.timestamp is not None and not (start <= item.timestamp <= end):
            item.verdict="rejected_outside_metadata_interval"; item.reasons.append("timestamp_outside_metadata_interval")
        elif item.configuration_fields and not item.counters and not item.assertions:
            item.verdict="rejected_configuration_only"; item.reasons.append("configuration_field_not_transfer_evidence")
        elif not ({"payload_semantic","probe"} & set(item.scope_tags)):
            item.verdict="rejected_unscoped"; item.reasons.append("no_probe_or_payload_semantic_scope")
        else:
            matches: List[Attempt]=[]
            identity_conflicts=0
            for attempt in attempts:
                if item.timestamp is not None and attempt.records:
                    lower=attempt.records[0].timestamp-dt.timedelta(seconds=1)
                    upper=attempt.records[-1].timestamp+dt.timedelta(seconds=2)
                    if not (lower <= item.timestamp <= upper): continue
                overlap=0; compatible=True
                for key,value in item.identity_fields.items():
                    if key not in attempt.fields: continue
                    overlap += 1
                    if not values_compatible(key,attempt.fields[key],value): compatible=False; break
                if not compatible:
                    identity_conflicts += 1; continue
                if item.identity_fields and overlap==0: continue
                matches.append(attempt)
            if not item.identity_fields and item.timestamp is None:
                strong_summary = "probe" in item.scope_tags and ("summary_member" in item.scope_tags or bool(item.assertions) or len(item.counters)>=2)
                matches = lifecycle_attempts if strong_summary and len(lifecycle_attempts)==1 else []
            if not matches:
                item.verdict="rejected_identity_or_time_mismatch" if identity_conflicts else "rejected_uncorrelated"
                item.reasons.append("identity_conflict" if identity_conflicts else "no_unique_attempt_match")
            elif len(matches)>1:
                item.verdict="rejected_ambiguous_attempt"; item.reasons.append("multiple_compatible_attempts")
            else:
                attempt=matches[0]; item.correlated_attempt_ids=[attempt.attempt_id]; attempt.zero_candidates.append(item)
                if item.contradicts_zero():
                    item.verdict="correlated_contradiction"; item.reasons.append("positive_payload_counter_or_assertion")
                elif item.proof_capable():
                    item.verdict="accepted_zero_proof_candidate"; item.reasons.append("proof_capable_zero_counter_or_assertion")
                elif item.corroborates_zero():
                    item.verdict="accepted_zero_corroboration"; item.reasons.append("zero_only_corroboration_not_sufficient_alone")
                else:
                    item.verdict="rejected_insufficient_zero_semantics"; item.reasons.append("candidate_lacks_zero_proof_semantics")
        verdicts[item.verdict]+=1
        for reason in item.reasons: reasons[reason]+=1
    return {"candidate_count":len(candidates),"verdict_counts":dict(sorted(verdicts.items())),"reason_counts":dict(sorted(reasons.items())),"proof_candidate_count":verdicts.get("accepted_zero_proof_candidate",0),"corroborating_candidate_count":verdicts.get("accepted_zero_corroboration",0),"contradiction_candidate_count":verdicts.get("correlated_contradiction",0),"rejected_candidate_count":sum(v for k,v in verdicts.items() if k.startswith("rejected_"))}

def record_private(record: EvidenceRecord) -> Dict[str, Any]:
    return {"timestamp_utc": record.timestamp.isoformat().replace("+00:00", "Z"), "event_type": record.event_type, "client_semantic": record.client, "fields": record.fields, "canonical_body": record.body, "fingerprint_sha256": record.fingerprint, "sources": record.sources}


def candidate_private(item: ZeroCandidate) -> Dict[str, Any]:
    return {"fingerprint_sha256":item.fingerprint,"counters":item.counters,"assertions":item.assertions,"identity_fields":item.identity_fields,"timestamp_utc":item.timestamp.isoformat().replace("+00:00","Z") if item.timestamp else None,"raw_text":item.raw_text,"scope_tags":item.scope_tags,"configuration_fields":item.configuration_fields,"sources":item.sources,"verdict":item.verdict,"reasons":item.reasons,"correlated_attempt_ids":item.correlated_attempt_ids,"proof_capable":item.proof_capable(),"contradicts_zero":item.contradicts_zero()}

def token(prefix: str, value: str) -> str:
    return f"{prefix}-sha256:{sha256_bytes(value.encode())[:16]}"

def sanitize_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    result=dict(fields)
    if "endpoint" in result: result["endpoint"]=token("endpoint",str(result["endpoint"]))
    if "requested_service_uuid" in result: result["requested_service_uuid"]=token("uuid",str(result["requested_service_uuid"]))
    return result

def candidate_public(item: ZeroCandidate) -> Dict[str, Any]:
    return {"fingerprint_sha256":item.fingerprint,"counters":item.counters,"assertions":item.assertions,"identity_fields":sanitize_fields(item.identity_fields),"timestamp_utc":item.timestamp.isoformat().replace("+00:00","Z") if item.timestamp else None,"scope_tags":item.scope_tags,"configuration_field_names":sorted(item.configuration_fields),"source_fingerprints":[sha256_bytes((str(x.get("source"))+":"+str(x.get("location"))).encode()) for x in item.sources],"verdict":item.verdict,"reasons":item.reasons,"correlated_attempt_ids":item.correlated_attempt_ids,"proof_capable":item.proof_capable(),"contradicts_zero":item.contradicts_zero()}

def attempt_private(attempt: Attempt) -> Dict[str, Any]:
    pair=attempt.lifecycle_pair(); zero=attempt.zero_payload_result()
    return {"attempt_id":attempt.attempt_id,"accepted_full_closure":attempt.accepted(),"gate_projection":attempt.gate_projection(),"client_semantic":attempt.client_semantic(),"tuple_complete":attempt.tuple_complete(),"expected_values_match":attempt.expected_match(),"lifecycle_matched":pair is not None,"lifecycle_pair":[pair[0].fingerprint,pair[1].fingerprint] if pair else None,"zero_payload":zero,"fields":attempt.fields,"conflicts":attempt.conflicts,"records":[record_private(r) for r in attempt.records],"zero_payload_candidate_fingerprints":[c.fingerprint for c in attempt.zero_candidates]}

def attempt_public(attempt: Attempt) -> Dict[str, Any]:
    pair=attempt.lifecycle_pair(); zero=attempt.zero_payload_result()
    return {"attempt_id":attempt.attempt_id,"accepted_full_closure":attempt.accepted(),"gate_projection":attempt.gate_projection(),"client_semantic":attempt.client_semantic(),"tuple_complete":attempt.tuple_complete(),"expected_values_match":attempt.expected_match(),"lifecycle_matched":pair is not None,"zero_payload":zero,"fields":sanitize_fields(attempt.fields),"event_fingerprints":[r.fingerprint for r in attempt.records],"zero_payload_candidate_fingerprints":[c.fingerprint for c in attempt.zero_candidates]}

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text.rstrip() + "\n", encoding="utf-8")


def manifest(root: Path, destination: Path) -> None:
    lines = [f"{sha256_file(p)}  {p.relative_to(root)}" for p in sorted(root.rglob("*")) if p.is_file() and p != destination]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_zip(root: Path, destination: Path, arc_root: Optional[str] = None) -> None:
    if destination.exists(): destination.unlink()
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(root.rglob("*")):
            if not path.is_file(): continue
            relative = path.relative_to(root); arcname = str(Path(arc_root) / relative) if arc_root else str(relative)
            info = zipfile.ZipInfo(arcname, date_time=(2026, 7, 27, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def privacy_gate(publication: Path, raw_values: Sequence[str]) -> List[str]:
    violations: List[str] = []
    for path in publication.rglob("*"):
        if not path.is_file(): continue
        data = path.read_bytes(); text = safe_text(data) or ""
        for value in raw_values:
            if value and value.encode() in data: violations.append(f"{path.name}:raw-value")
        if RAW_MAC_RE.search(text): violations.append(f"{path.name}:raw-mac")
        if UUID128_RE.search(text): violations.append(f"{path.name}:raw-uuid")
        if re.search(r"/Users/[^/\s]+|[A-Za-z]:\\Users\\", text): violations.append(f"{path.name}:absolute-user-path")
    return sorted(set(violations))


def render_markdown(public: Dict[str, Any]) -> str:
    attempt=public.get("primary_attempt") or {}
    fields=attempt.get("fields",{})
    gates=attempt.get("gate_projection",{})
    zero=attempt.get("zero_payload",{})
    census=public.get("zero_payload_source_census",{})
    def yn(key: str) -> str: return "YES" if gates.get(key) else "NO"
    return f"""# {RELEASE} — Attempt-Level Gate Projection and Zero-Payload Census

## Disposition

**{public['acceptance']}**

Qualification outcome: `{public['qualification_outcome']}`

The locked archive was reanalyzed offline. No phone or glasses contact occurs.

## Attempt-level closure gates

- Client-side RFCOMM semantic: **{yn('client_semantic')}**
- Complete expected tuple: **{yn('tuple_complete')}**
- Expected values match: **{yn('expected_values_match')}**
- Conflict-free identity: **{yn('conflict_free')}**
- Matching explicit open/close: **{yn('matching_open_close')}**
- RFCOMM lifecycle closure proven: **{yn('lifecycle_closure_proven')}**
- No payload data event observed: **{yn('no_payload_data_event_observed')}**
- No positive payload counter observed: **{yn('no_positive_payload_counter_observed')}**
- Explicit zero-payload proof: **{yn('explicit_zero_payload_proven')}**
- Full zero-payload closure: **{yn('full_zero_payload_closure_proven')}**

## Archive-wide zero-payload source census

- Members scanned: **{census.get('members_scanned',0)}**
- Lines scanned: **{census.get('lines_scanned',0)}**
- Deduplicated candidates: **{census.get('deduplicated_candidates',0)}**
- Accepted proof candidates: **{census.get('proof_candidate_count',0)}**
- Accepted corroborating candidates: **{census.get('corroborating_candidate_count',0)}**
- Correlated contradictions: **{census.get('contradiction_candidate_count',0)}**
- Rejected candidates: **{census.get('rejected_candidate_count',0)}**

## Bounded runtime tuple

| Field | Value |
|---|---:|
| Endpoint | {fields.get('endpoint','UNRESOLVED')} |
| Requested service UUID | {fields.get('requested_service_uuid','UNRESOLVED')} |
| Native service class UUID | {fields.get('native_service_class_uuid','UNRESOLVED')} |
| Probe UID/PID | {fields.get('uid','UNRESOLVED')} / {fields.get('pid','UNRESOLVED')} |
| Slot / handle | {fields.get('slot','UNRESOLVED')} / {fields.get('port_handle','UNRESOLVED')} |
| SCN / DLCI / MTU | {fields.get('scn','UNRESOLVED')} / {fields.get('dlci','UNRESOLVED')} / {fields.get('mtu','UNRESOLVED')} |

## Zero-payload diagnostics

- Payload data-event count: **{zero.get('payload_data_event_count',0)}**
- Proof candidate count: **{zero.get('proof_candidate_count',0)}**
- Corroborating candidate count: **{zero.get('corroborating_candidate_count',0)}**
- Contradiction candidate count: **{zero.get('contradiction_candidate_count',0)}**
- Positive counters: `{json.dumps(zero.get('positive_counters',{}),sort_keys=True)}`
- Zero counters: `{json.dumps(zero.get('zero_counters',{}),sort_keys=True)}`

Absence of payload events is corroboration only. Full zero-payload closure requires an accepted explicit assertion, bidirectional zero-byte counters, or an aggregate zero-payload counter correlated to the same attempt.
"""

def determine_disposition(attempts: List[Attempt]) -> Tuple[str,str,Optional[Attempt],List[Attempt],List[Attempt]]:
    full=[a for a in attempts if a.accepted()]
    lifecycle=[a for a in attempts if a.lifecycle_qualified()]
    primary=lifecycle[0] if len(lifecycle)==1 else (full[0] if len(full)==1 else None)
    if len(full)==1 and len(lifecycle)==1: return FULL_ACCEPTANCE,FULL_OUTCOME,primary,full,lifecycle
    if len(lifecycle)==1: return LIFECYCLE_ACCEPTANCE,LIFECYCLE_OUTCOME,primary,full,lifecycle
    return FAIL_ACCEPTANCE,FAIL_OUTCOME,primary,full,lifecycle

def run_analysis(source_zip: Path, output: Path, expected_sha: Optional[str]) -> Dict[str, Any]:
    if not source_zip.is_file(): raise AnalysisError(f"Source private archive not found: {source_zip}")
    source_sha=sha256_file(source_zip)
    if expected_sha and source_sha.lower()!=expected_sha.lower(): raise AnalysisError(f"Source archive SHA-256 mismatch: expected {expected_sha}, observed {source_sha}")
    start,end,interval_sources=discover_interval(source_zip)
    records,stats,timebase=collect_records(source_zip,start,end)
    candidates,census_scan=extract_zero_payload_candidates(source_zip,start,end,timebase)
    attempts=group_attempts(records)
    census_diag=correlate_zero_candidates(attempts,candidates,start,end)
    acceptance,outcome,primary,full_attempts,lifecycle_attempts=determine_disposition(attempts)
    census={**census_scan,**census_diag}
    output.mkdir(parents=True,exist_ok=False); analysis_dir=output/'analysis'; publication_dir=output/'publication'; analysis_dir.mkdir(); publication_dir.mkdir()
    private={"schema":SCHEMA_PRIVATE,"source_private_archive":{"filename":source_zip.name,"sha256":source_sha},"metadata_interval":{"start_utc":start.isoformat().replace('+00:00','Z'),"end_utc":end.isoformat().replace('+00:00','Z'),**interval_sources},"timebase_provenance":timebase.as_dict(),"selection_stats":stats,"attempt_count":len(attempts),"lifecycle_qualified_attempt_count":len(lifecycle_attempts),"accepted_attempt_count":len(full_attempts),"qualification_outcome":outcome,"acceptance":acceptance,"attempts":[attempt_private(a) for a in attempts],"zero_payload_source_census":census,"zero_payload_candidates":[candidate_private(c) for c in candidates]}
    write_json(analysis_dir/'r25.2.2.2.1.3-private-analysis.json',private)
    primary_public=attempt_public(primary) if primary else None
    public={"schema":SCHEMA_PUBLIC,"source_private_archive_sha256":source_sha,"metadata_interval":{"start_utc":start.isoformat().replace('+00:00','Z'),"end_utc":end.isoformat().replace('+00:00','Z')},"evidence_controls":{"metadata_interval_enforced":True,"attempt_level_gate_projection":True,"archive_wide_zero_payload_source_census":True,"candidate_rejection_diagnostics":True,"existing_evidence_counter_assertion_correlation":True,"bluetooth_scoped_extraction":True,"cross_source_canonical_deduplication":True,"offline_only":True,"absence_of_data_events_is_corroboration_only":True},"timebase_provenance":timebase.as_dict(),"selection_stats":stats,"attempt_count":len(attempts),"lifecycle_qualified_attempt_count":len(lifecycle_attempts),"accepted_attempt_count":len(full_attempts),"qualification_outcome":outcome,"acceptance":acceptance,"primary_attempt":primary_public,"attempts":[attempt_public(a) for a in attempts],"zero_payload_source_census":census,"zero_payload_candidate_diagnostics":[candidate_public(c) for c in candidates],"expected_runtime_tuple":{**{k:v for k,v in EXPECTED.items() if k!='requested_service_uuid'},"requested_service_uuid":token('uuid',EXPECTED['requested_service_uuid'])}}
    write_json(publication_dir/'r25.2.2.2.1.3-attempt-gates-and-zero-payload-census.json',public)
    write_text(publication_dir/'r25.2.2.2.1.3-attempt-gates-and-zero-payload-census.md',render_markdown(public))
    gates=primary_public.get('gate_projection',{}) if primary_public else {}
    write_json(publication_dir/'runtime-status-summary.json',{"schema":SCHEMA_STATUS,"release":RELEASE,"acceptance":acceptance,"qualification_outcome":outcome,"attempt_count":len(attempts),"lifecycle_qualified_attempt_count":len(lifecycle_attempts),"accepted_attempt_count":len(full_attempts),"rfcomm_client_semantic_confirmed":bool(gates.get('client_semantic')),"same_attempt_runtime_tuple_confirmed":bool(gates.get('tuple_complete') and gates.get('expected_values_match')),"matching_open_close_confirmed":bool(gates.get('matching_open_close')),"rfcomm_lifecycle_closure_confirmed":bool(gates.get('lifecycle_closure_proven')),"no_payload_data_event_observed":bool(gates.get('no_payload_data_event_observed')),"zero_payload_confirmed":bool(gates.get('explicit_zero_payload_proven')),"full_zero_payload_closure_confirmed":bool(gates.get('full_zero_payload_closure_proven')),"zero_payload_candidate_census":census,"offline_regeneration":True,"timebase_method":timebase.method,"threadtime_utc_offset_minutes":timebase.offset_minutes,"semantic_offset_maximization_used":False})
    write_text(publication_dir/'methodology.md',"""# Methodology

1. Verify the locked private-archive hash and exact metadata interval.
2. Reconstruct Bluetooth/RFCOMM attempts using the accepted epoch/threadtime and lifecycle-correlation repairs.
3. Project every attempt-level closure gate independently; zero-payload failure cannot erase lifecycle or tuple proof.
4. Scan every text-like archive member, including nested ZIPs, for transfer counters and explicit payload assertions.
5. Retain configuration-only candidates such as `max_rx_packet_size=0`, but reject them as transfer evidence.
6. Correlate candidates by interval, timestamp, tuple identity, and unique lifecycle.
7. Retain accepted, corroborating, contradictory, and rejected candidates with machine-readable reasons.
8. Treat absence of payload events only as corroboration.
9. Promote full closure only with one lifecycle-qualified attempt and proof-capable zero evidence without contradictions.
10. Otherwise publish bounded lifecycle-only closure when that is the strongest defensible result.
""")
    write_text(publication_dir/'limitations.md',"""# Limitations

A full PASS is limited to the locked archive and its metadata interval. Zero payload requires an accepted explicit assertion, bidirectional zero-byte counters, or an aggregate zero-payload counter correlated to the same attempt. Configuration values, callback counts alone, and absence of data events are not sufficient. If the archive-wide census finds no proof-capable evidence, the result remains bounded lifecycle-only closure and a new instrumented capture is required for full zero-payload promotion.
""")
    raw_values=[]
    for a in attempts: raw_values.extend(str(v) for k,v in a.fields.items() if k in {'endpoint','requested_service_uuid'})
    violations=privacy_gate(publication_dir,raw_values)
    if violations: raise AnalysisError('Sanitized publication privacy gate failed: '+', '.join(violations))
    manifest(publication_dir,publication_dir/'evidence-hashes.txt'); manifest(output,output/'SHA256SUMS-private.txt')
    make_zip(publication_dir,output.with_name(output.name+'-sanitized-publication.zip'),arc_root=publication_dir.name)
    make_zip(output,output.with_name(output.name+'-private-analysis.zip'),arc_root=output.name)
    print(f"R25_2_2_2_1_3_SOURCE_PRIVATE_ZIP_SHA256={source_sha}")
    print(f"R25_2_2_2_1_3_METADATA_INTERVAL_START={start.isoformat().replace('+00:00','Z')}")
    print(f"R25_2_2_2_1_3_METADATA_INTERVAL_END={end.isoformat().replace('+00:00','Z')}")
    print(f"R25_2_2_2_1_3_TIMEBASE_METHOD={timebase.method}")
    print("R25_2_2_2_1_3_ATTEMPT_LEVEL_GATE_PROJECTION=PASS")
    print("R25_2_2_2_1_3_ARCHIVE_WIDE_ZERO_PAYLOAD_CENSUS=PASS")
    print("R25_2_2_2_1_3_CANDIDATE_REJECTION_DIAGNOSTICS=PASS")
    print(f"R25_2_2_2_1_3_ATTEMPT_COUNT={len(attempts)}")
    print(f"R25_2_2_2_1_3_LIFECYCLE_QUALIFIED_ATTEMPT_COUNT={len(lifecycle_attempts)}")
    print(f"R25_2_2_2_1_3_ACCEPTED_ATTEMPT_COUNT={len(full_attempts)}")
    print(f"R25_2_2_2_1_3_ZERO_PAYLOAD_CANDIDATE_COUNT={census['candidate_count']}")
    print(f"R25_2_2_2_1_3_ZERO_PAYLOAD_PROOF_CANDIDATE_COUNT={census['proof_candidate_count']}")
    print(f"R25_2_2_2_1_3_ZERO_PAYLOAD_REJECTED_CANDIDATE_COUNT={census['rejected_candidate_count']}")
    if primary_public:
        f=primary_public['fields']; g=primary_public['gate_projection']
        print(f"R25_2_2_2_1_3_ANDROID_CLIENT_SEMANTIC={'YES' if g['client_semantic'] else 'NO'}")
        print(f"R25_2_2_2_1_3_RUNTIME_TUPLE={'YES' if g['tuple_complete'] and g['expected_values_match'] else 'NO'}")
        print(f"R25_2_2_2_1_3_MATCHING_OPEN_CLOSE={'YES' if g['matching_open_close'] else 'NO'}")
        print(f"R25_2_2_2_1_3_LIFECYCLE_CLOSURE={'YES' if g['lifecycle_closure_proven'] else 'NO'}")
        print(f"R25_2_2_2_1_3_NO_PAYLOAD_EVENT_OBSERVED={'YES' if g['no_payload_data_event_observed'] else 'NO'}")
        print(f"R25_2_2_2_1_3_EXPLICIT_ZERO_PAYLOAD={'YES' if g['explicit_zero_payload_proven'] else 'NO'}")
        print(f"R25_2_2_2_1_3_PROBE_UID={f.get('uid')}"); print(f"R25_2_2_2_1_3_PROBE_PID={f.get('pid')}")
        print(f"R25_2_2_2_1_3_SLOT={f.get('slot')}"); print(f"R25_2_2_2_1_3_PORT_HANDLE={f.get('port_handle')}")
        print(f"R25_2_2_2_1_3_SCN={f.get('scn')}"); print(f"R25_2_2_2_1_3_DLCI={f.get('dlci')}"); print(f"R25_2_2_2_1_3_MTU={f.get('mtu')}")
    print(f"R25_2_2_2_1_3_QUALIFICATION_OUTCOME={outcome}")
    print(f"R1_3_3_2_25_2_2_2_1_3_ACCEPTANCE={acceptance}")
    print(f"R25_2_2_2_1_3_OUTPUT={output}")
    return public

def main(argv: Optional[Sequence[str]]=None) -> int:
    parser=argparse.ArgumentParser(description='Offline r25.2.2.2.1.3 attempt-gate and zero-payload census repair')
    parser.add_argument('--source-private-zip',required=True,type=Path); parser.add_argument('--expected-source-sha256'); parser.add_argument('--output',required=True,type=Path); parser.add_argument('--repo',type=Path)
    args=parser.parse_args(argv)
    try: public=run_analysis(args.source_private_zip.expanduser(),args.output.expanduser(),args.expected_source_sha256)
    except AnalysisError as error:
        print('R1_3_3_2_25_2_2_2_1_3_ACCEPTANCE=FAIL',file=sys.stderr); print(f'ERROR: {error}',file=sys.stderr); return 2
    return 0 if public['acceptance'] in {FULL_ACCEPTANCE,LIFECYCLE_ACCEPTANCE} else 1

if __name__=='__main__': raise SystemExit(main())
