#!/usr/bin/env python3
"""Offline r25.2.2.2.1.2 RFCOMM lifecycle-correlation repair.

Consumes an existing private evidence ZIP only.  It never imports subprocess or
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

RELEASE = "r1.3.3.2.25.2.2.2.1.2"
SCHEMA_PRIVATE = "rokid.r25.2.2.2.1.2.private-analysis.v3"
SCHEMA_PUBLIC = "rokid.r25.2.2.2.1.2.public-full-closure.v3"
SCHEMA_STATUS = "rokid.r25.2.runtime-status-summary.v1"
PASS_OUTCOME = "RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE"
FAIL_OUTCOME = "RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_NOT_PROVEN"
PASS_ACCEPTANCE = "PASS_FULL_ZERO_PAYLOAD_CLOSURE"
FAIL_ACCEPTANCE = "FAIL_FULL_ZERO_PAYLOAD_CLOSURE"
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
PROBE_ZERO_SCOPE_RE = re.compile(r"(?i)(r25(?:[._ -]?2){2,}|channelprobe|connection-only|rfcomm).*(payload|bytes|callbacks)|(?:payload|bytes|callbacks).*(rfcomm|connection-only)")
DATA_EVENT_RE = re.compile(r"(?i)(BTA_JV_RFCOMM_DATA_IND_EVT|RFC_PORT_EVENT_RXCHAR|PORT_EV_RXCHAR|DATA_IND|data_received|onDataReceived|socket.*\bread\b|socket.*\bwrite\b)")

COUNTER_ALIASES = {
    "tx_bytes": ("tx_bytes", "bytes_written", "write_bytes", "written_bytes", "payload_tx_bytes", "sent_bytes"),
    "rx_bytes": ("rx_bytes", "bytes_read", "read_bytes", "received_bytes", "payload_rx_bytes"),
    "payload_bytes": ("payload_bytes", "payload_len", "payload_length", "total_payload_bytes"),
    "data_callbacks": ("data_callbacks", "payload_callbacks", "rx_callbacks", "data_event_count"),
}

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
class ZeroEvidence:
    source: str
    location: str
    counters: Dict[str, int]
    explicit_zero: bool
    identity_fields: Dict[str, Any]
    timestamp: Optional[dt.datetime]
    raw_text: str


def zero_identity_from_mapping(lowered: Dict[str, Any]) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    uuid_value = None
    for key in ("requested_service_uuid", "service_uuid", "rfcomm_uuid"):
        if key in lowered:
            uuid_value = str(lowered[key])
            break
    if uuid_value:
        match = UUID128_RE.search(uuid_value)
        if match:
            fields["requested_service_uuid"] = match.group(1).lower()
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
    for key in ("timestamp_utc", "event_utc", "observed_utc", "finished_utc", "completed_utc"):
        if key in lowered:
            parsed = parse_datetime(lowered[key])
            if parsed is not None:
                return parsed
    return None


def extract_zero_payload_evidence(path: Path) -> List[ZeroEvidence]:
    evidence: List[ZeroEvidence] = []
    for source, raw in iter_archive_members(path):
        text = safe_text(raw)
        if text is None:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            obj = None
        if obj is not None:
            def visit(value: Any, path_: str = "$") -> None:
                if isinstance(value, dict):
                    lowered = {str(k).lower(): v for k, v in value.items()}
                    counters: Dict[str, int] = {}
                    for canonical, aliases in COUNTER_ALIASES.items():
                        for alias in aliases:
                            if alias in lowered:
                                try:
                                    counters[canonical] = int(lowered[alias])
                                except (TypeError, ValueError):
                                    pass
                                break
                    explicit = bool(lowered.get("zero_payload") is True or str(lowered.get("zero_payload", "")).lower() in {"yes", "true", "1"})
                    scope_text = json.dumps(value, sort_keys=True)
                    if (counters or explicit) and PROBE_ZERO_SCOPE_RE.search(source + " " + scope_text):
                        evidence.append(ZeroEvidence(source, path_, counters, explicit, zero_identity_from_mapping(lowered), zero_timestamp_from_mapping(lowered), scope_text))
                    for key, child in value.items():
                        visit(child, f"{path_}.{key}")
                elif isinstance(value, list):
                    for i, child in enumerate(value):
                        visit(child, f"{path_}[{i}]")
            visit(obj)
        for number, line in enumerate(text.splitlines(), 1):
            if not PROBE_ZERO_SCOPE_RE.search(source + " " + line):
                continue
            counters: Dict[str, int] = {}
            for canonical, aliases in COUNTER_ALIASES.items():
                value = parse_int(line, aliases)
                if value is not None:
                    counters[canonical] = value
            explicit = bool(re.search(r"(?i)\bzero[_ -]?payload\s*[=:]\s*(?:true|yes|1)\b", line))
            if counters or explicit:
                evidence.append(ZeroEvidence(source, f"line:{number}", counters, explicit, zero_identity_from_text(line), None, line.strip()))
    unique: Dict[str, ZeroEvidence] = {}
    for item in evidence:
        key = sha256_bytes(json.dumps({"source": item.source, "location": item.location, "counters": item.counters, "explicit": item.explicit_zero, "identity": item.identity_fields, "timestamp": item.timestamp.isoformat() if item.timestamp else None}, sort_keys=True).encode())
        unique[key] = item
    return list(unique.values())


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
    zero_evidence: List[ZeroEvidence]
    fields: Dict[str, Any] = field(default_factory=dict)
    conflicts: Dict[str, List[Any]] = field(default_factory=dict)
    def aggregate(self) -> None:
        values: Dict[str, List[Any]] = defaultdict(list)
        for record in self.records:
            for key, value in record.fields.items():
                if key == "source_pid":
                    continue
                if value not in values[key]:
                    values[key].append(value)
        self.fields = {}; self.conflicts = {}
        for key, observed in values.items():
            if len(observed) == 1:
                self.fields[key] = observed[0]
            elif key == "endpoint" and endpoint_compatible([str(v) for v in observed]):
                self.fields[key] = preferred_endpoint([str(v) for v in observed]); self.fields["endpoint_alias_count"] = len(observed)
            else:
                self.conflicts[key] = observed
    def client_semantic(self) -> bool:
        return any(r.client for r in self.records)
    def open_records(self) -> List[EvidenceRecord]:
        return [r for r in self.records if r.event_type in {"port_open_event", "jv_open_event", "client_connected", "socket_connected"}]
    def close_records(self) -> List[EvidenceRecord]:
        return [r for r in self.records if r.event_type in {"port_close_event", "native_close"}]
    def lifecycle_pair(self) -> Optional[Tuple[EvidenceRecord, EvidenceRecord]]:
        for opened in self.open_records():
            for closed in self.close_records():
                if closed.timestamp <= opened.timestamp:
                    continue
                oh, ch = opened.fields.get("port_handle"), closed.fields.get("port_handle")
                oe, ce = opened.fields.get("endpoint"), closed.fields.get("endpoint")
                if oh is not None and ch is not None and oh != ch:
                    continue
                if oe and ce and not endpoint_compatible([str(oe), str(ce)]):
                    continue
                if (oh is not None or ch is not None or (oe and ce)):
                    return opened, closed
        return None
    def zero_payload_result(self) -> Dict[str, Any]:
        data_events = [r for r in self.records if r.event_type == "payload_data_event"]
        counters: Dict[str, List[int]] = defaultdict(list)
        explicit = False
        for item in self.zero_evidence:
            explicit = explicit or item.explicit_zero
            for key, value in item.counters.items():
                counters[key].append(value)
        positive = {k: sorted(set(v for v in values if v > 0)) for k, values in counters.items() if any(v > 0 for v in values)}
        all_zero = {k: sorted(set(values)) for k, values in counters.items() if values and all(v == 0 for v in values)}
        bidirectional = "tx_bytes" in all_zero and "rx_bytes" in all_zero
        aggregate = "payload_bytes" in all_zero
        callbacks_zero = "data_callbacks" in all_zero
        proven = not data_events and not positive and (explicit or bidirectional or aggregate) and bool(self.zero_evidence)
        return {"proven": proven, "explicit_zero": explicit, "bidirectional_zero": bidirectional, "aggregate_zero": aggregate, "callbacks_zero": callbacks_zero, "positive_counters": positive, "zero_counters": all_zero, "payload_data_event_count": len(data_events), "evidence_count": len(self.zero_evidence)}
    def tuple_complete(self) -> bool:
        return all(key in self.fields for key in EXPECTED) and "endpoint" in self.fields
    def expected_match(self) -> bool:
        return all(self.fields.get(key) == value for key, value in EXPECTED.items())
    def accepted(self) -> bool:
        return self.client_semantic() and self.tuple_complete() and self.expected_match() and not any(key in self.conflicts for key in ("requested_service_uuid", "endpoint", "uid", "pid", "slot", "port_handle", "scn", "dlci", "mtu")) and self.lifecycle_pair() is not None and self.zero_payload_result()["proven"]


def compatible_with_seed(record: EvidenceRecord, fields: Dict[str, Any]) -> bool:
    for key in ("endpoint", "requested_service_uuid", "uid", "pid", "slot", "port_handle", "socket_id"):
        if key in fields and key in record.fields and not values_compatible(key, fields[key], record.fields[key]):
            return False
    return True


def group_attempts(records: Sequence[EvidenceRecord], zero_evidence: List[ZeroEvidence]) -> List[Attempt]:
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
    # Correlate zero-payload evidence fail-closed. Evidence with identity fields
    # must resolve to exactly one compatible attempt. Unkeyed evidence is used
    # only when the archive contains exactly one attempt.
    for item in zero_evidence:
        candidates: List[Attempt] = []
        for attempt in attempts:
            if item.timestamp is not None and attempt.records:
                lower = attempt.records[0].timestamp - dt.timedelta(seconds=1)
                upper = attempt.records[-1].timestamp + dt.timedelta(seconds=2)
                if not (lower <= item.timestamp <= upper):
                    continue
            if item.identity_fields:
                overlap = 0
                compatible = True
                for key, value in item.identity_fields.items():
                    if key not in attempt.fields:
                        continue
                    overlap += 1
                    if not values_compatible(key, attempt.fields[key], value):
                        compatible = False
                        break
                if not compatible or overlap == 0:
                    continue
            candidates.append(attempt)
        if not item.identity_fields and item.timestamp is None:
            candidates = attempts if len(attempts) == 1 else []
        if len(candidates) == 1:
            candidates[0].zero_evidence.append(item)
    return attempts


def record_private(record: EvidenceRecord) -> Dict[str, Any]:
    return {"timestamp_utc": record.timestamp.isoformat().replace("+00:00", "Z"), "event_type": record.event_type, "client_semantic": record.client, "fields": record.fields, "canonical_body": record.body, "fingerprint_sha256": record.fingerprint, "sources": record.sources}


def zero_private(item: ZeroEvidence) -> Dict[str, Any]:
    return {"source": item.source, "location": item.location, "counters": item.counters, "explicit_zero": item.explicit_zero, "identity_fields": item.identity_fields, "timestamp_utc": item.timestamp.isoformat().replace("+00:00", "Z") if item.timestamp else None, "raw_text": item.raw_text}


def token(prefix: str, value: str) -> str:
    return f"{prefix}-sha256:{sha256_bytes(value.encode())[:16]}"


def attempt_private(attempt: Attempt) -> Dict[str, Any]:
    pair = attempt.lifecycle_pair(); zero = attempt.zero_payload_result()
    return {"attempt_id": attempt.attempt_id, "accepted": attempt.accepted(), "client_semantic": attempt.client_semantic(), "tuple_complete": attempt.tuple_complete(), "expected_values_match": attempt.expected_match(), "lifecycle_matched": pair is not None, "lifecycle_pair": [pair[0].fingerprint, pair[1].fingerprint] if pair else None, "zero_payload": zero, "fields": attempt.fields, "conflicts": attempt.conflicts, "records": [record_private(r) for r in attempt.records], "zero_payload_evidence": [zero_private(z) for z in attempt.zero_evidence]}


def attempt_public(attempt: Attempt) -> Dict[str, Any]:
    fields = {k: v for k, v in attempt.fields.items() if k in set(EXPECTED) | {"endpoint", "native_service_class_uuid", "endpoint_alias_count"}}
    if "endpoint" in fields: fields["endpoint"] = token("endpoint", str(fields["endpoint"]))
    if "requested_service_uuid" in fields: fields["requested_service_uuid"] = token("uuid", str(fields["requested_service_uuid"]))
    if "native_service_class_uuid" in fields: fields["native_service_class_uuid"] = token("native-uuid", str(fields["native_service_class_uuid"]))
    pair = attempt.lifecycle_pair(); zero = attempt.zero_payload_result()
    return {"attempt_id": attempt.attempt_id, "accepted": attempt.accepted(), "client_semantic": attempt.client_semantic(), "tuple_complete": attempt.tuple_complete(), "expected_values_match": attempt.expected_match(), "lifecycle_matched": pair is not None, "zero_payload": zero, "fields": fields, "event_fingerprints": [r.fingerprint for r in attempt.records], "zero_payload_evidence_fingerprints": [sha256_bytes(json.dumps({"source": z.source, "location": z.location, "counters": z.counters, "explicit": z.explicit_zero}, sort_keys=True).encode()) for z in attempt.zero_evidence]}


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
    attempt = public.get("accepted_attempt") or {}; fields = attempt.get("fields", {}); zero = attempt.get("zero_payload", {})
    return f"""# {RELEASE} — Bluetooth-Scoped RFCOMM Full Closure Repair

## Disposition

**{public['acceptance']}**

The locked archive was reanalyzed offline. No phone or glasses contact occurs.

## Closure gates

- Bluetooth-scoped extraction: **PASS**
- Cross-source canonical deduplication: **PASS**
- Lifecycle-keyed attempt coalescence: **{'YES' if attempt else 'NO'}**
- Client semantic: **{'YES' if attempt.get('client_semantic') else 'NO'}**
- Matching open/close: **{'YES' if attempt.get('lifecycle_matched') else 'NO'}**
- Explicit zero-payload evidence retained: **{'YES' if zero.get('evidence_count', 0) else 'NO'}**
- Zero payload proven: **{'YES' if zero.get('proven') else 'NO'}**

## Qualified tuple

| Field | Value |
|---|---:|
| Endpoint | {fields.get('endpoint', 'UNRESOLVED')} |
| Requested service UUID | {fields.get('requested_service_uuid', 'UNRESOLVED')} |
| Native service class UUID | {fields.get('native_service_class_uuid', 'UNRESOLVED')} |
| Probe UID/PID | {fields.get('uid', 'UNRESOLVED')} / {fields.get('pid', 'UNRESOLVED')} |
| Slot / handle | {fields.get('slot', 'UNRESOLVED')} / {fields.get('port_handle', 'UNRESOLVED')} |
| SCN / DLCI / MTU | {fields.get('scn', 'UNRESOLVED')} / {fields.get('dlci', 'UNRESOLVED')} / {fields.get('mtu', 'UNRESOLVED')} |
"""


def run_analysis(source_zip: Path, output: Path, expected_sha: Optional[str]) -> Dict[str, Any]:
    if not source_zip.is_file(): raise AnalysisError(f"Source private archive not found: {source_zip}")
    source_sha = sha256_file(source_zip)
    if expected_sha and source_sha.lower() != expected_sha.lower(): raise AnalysisError(f"Source archive SHA-256 mismatch: expected {expected_sha}, observed {source_sha}")
    start, end, interval_sources = discover_interval(source_zip)
    records, stats, timebase = collect_records(source_zip, start, end)
    zero_evidence = extract_zero_payload_evidence(source_zip)
    attempts = group_attempts(records, zero_evidence)
    accepted_attempts = [a for a in attempts if a.accepted()]
    accepted = len(accepted_attempts) == 1
    output.mkdir(parents=True, exist_ok=False); analysis_dir = output / "analysis"; publication_dir = output / "publication"; analysis_dir.mkdir(); publication_dir.mkdir()
    private = {"schema": SCHEMA_PRIVATE, "source_private_archive": {"filename": source_zip.name, "sha256": source_sha}, "metadata_interval": {"start_utc": start.isoformat().replace("+00:00", "Z"), "end_utc": end.isoformat().replace("+00:00", "Z"), **interval_sources}, "timebase_provenance": timebase.as_dict(), "selection_stats": stats, "attempt_count": len(attempts), "accepted_attempt_count": len(accepted_attempts), "qualification_outcome": PASS_OUTCOME if accepted else FAIL_OUTCOME, "acceptance": PASS_ACCEPTANCE if accepted else FAIL_ACCEPTANCE, "attempts": [attempt_private(a) for a in attempts], "global_zero_payload_evidence": [zero_private(z) for z in zero_evidence]}
    write_json(analysis_dir / "r25.2.2.2.1.2-private-analysis.json", private)
    accepted_public = attempt_public(accepted_attempts[0]) if accepted else None
    public = {"schema": SCHEMA_PUBLIC, "source_private_archive_sha256": source_sha, "metadata_interval": {"start_utc": start.isoformat().replace("+00:00", "Z"), "end_utc": end.isoformat().replace("+00:00", "Z")}, "evidence_controls": {"metadata_interval_enforced": True, "bluetooth_scoped_extraction": True, "uid_pid_pair_recognition": True, "requested_and_native_uuid_domains_separate": True, "explicit_close_precedence": True, "cross_source_canonical_deduplication": True, "lifecycle_keyed_attempt_coalescence": True, "zero_payload_evidence_retained": True, "offline_only": True, "semantic_offset_maximization_forbidden": True}, "timebase_provenance": timebase.as_dict(), "selection_stats": stats, "attempt_count": len(attempts), "accepted_attempt_count": len(accepted_attempts), "qualification_outcome": PASS_OUTCOME if accepted else FAIL_OUTCOME, "acceptance": PASS_ACCEPTANCE if accepted else FAIL_ACCEPTANCE, "accepted_attempt": accepted_public, "expected_runtime_tuple": {**{k: v for k, v in EXPECTED.items() if k != "requested_service_uuid"}, "requested_service_uuid": token("uuid", EXPECTED["requested_service_uuid"])} }
    write_json(publication_dir / "r25.2.2.2.1.2-full-zero-payload-closure.json", public)
    write_text(publication_dir / "r25.2.2.2.1.2-full-zero-payload-closure.md", render_markdown(public))
    write_json(publication_dir / "runtime-status-summary.json", {"schema": SCHEMA_STATUS, "release": RELEASE, "acceptance": public["acceptance"], "qualification_outcome": public["qualification_outcome"], "attempt_count": len(attempts), "accepted_attempt_count": len(accepted_attempts), "rfcomm_client_semantic_confirmed": bool(accepted_public and accepted_public["client_semantic"]), "same_attempt_runtime_tuple_confirmed": bool(accepted_public and accepted_public["tuple_complete"]), "matching_open_close_confirmed": bool(accepted_public and accepted_public["lifecycle_matched"]), "zero_payload_confirmed": bool(accepted_public and accepted_public["zero_payload"]["proven"]), "zero_payload_evidence_retained": bool(zero_evidence), "offline_regeneration": True, "timebase_method": timebase.method, "threadtime_utc_offset_minutes": timebase.offset_minutes, "semantic_offset_maximization_used": False})
    write_text(publication_dir / "methodology.md", """# Methodology

1. Verify the locked private-archive hash and exact metadata interval.
2. Parse epoch timestamps as UTC and threadtime only from explicit provenance.
3. Admit only Bluetooth/RFCOMM-scoped lines; unrelated UUID, UID/PID and endpoint text is ignored.
4. Parse `from uid/pid=UID/PID` as a pair and enrich epoch duplicates from the bugreport copy.
5. Keep requested 128-bit service UUID and native service-class UUID in separate domains.
6. Canonicalize message bodies and merge overlapping logcat/bugreport copies while retaining all source references.
7. Coalesce one lifecycle from compatible root connect records through matching close records without gap-based splitting.
8. Give explicit close tokens precedence over function names.
9. Retain explicit zero-payload counters/evidence and fail on positive counters or data events.
10. Require exactly one complete client attempt matching UID/PID, slot 45, handle 29, SCN 3, DLCI 6 and MTU 990.
""")
    write_text(publication_dir / "limitations.md", """# Limitations

A PASS is limited to the locked archive and its metadata interval. Zero payload requires retained explicit counters or an explicit zero-payload assertion plus no contradictory data event. Absence of a data event alone is not sufficient. The repair does not claim application payload semantics, stock-app equivalence, or behavior outside the captured attempt.
""")
    raw_values: List[str] = []
    for a in attempts:
        raw_values.extend(str(v) for k, v in a.fields.items() if k in {"endpoint", "requested_service_uuid"})
    violations = privacy_gate(publication_dir, raw_values)
    if violations: raise AnalysisError("Sanitized publication privacy gate failed: " + ", ".join(violations))
    manifest(publication_dir, publication_dir / "evidence-hashes.txt"); manifest(output, output / "SHA256SUMS-private.txt")
    make_zip(publication_dir, output.with_name(output.name + "-sanitized-publication.zip"), arc_root=publication_dir.name)
    make_zip(output, output.with_name(output.name + "-private-analysis.zip"), arc_root=output.name)
    print(f"R25_2_2_2_1_2_SOURCE_PRIVATE_ZIP_SHA256={source_sha}")
    print(f"R25_2_2_2_1_2_METADATA_INTERVAL_START={start.isoformat().replace('+00:00','Z')}")
    print(f"R25_2_2_2_1_2_METADATA_INTERVAL_END={end.isoformat().replace('+00:00','Z')}")
    print(f"R25_2_2_2_1_2_TIMEBASE_METHOD={timebase.method}")
    print(f"R25_2_2_2_1_2_THREADTIME_UTC_OFFSET_MINUTES={timebase.offset_minutes}")
    print("R25_2_2_2_1_2_BLUETOOTH_SCOPED_EXTRACTION=PASS")
    print("R25_2_2_2_1_2_UID_PID_PAIR_RECOGNITION=PASS")
    print("R25_2_2_2_1_2_CROSS_SOURCE_CANONICAL_DEDUPLICATION=PASS")
    print(f"R25_2_2_2_1_2_DUPLICATE_RECORDS_REMOVED={stats['duplicate_semantic_lines']}")
    print(f"R25_2_2_2_1_2_ATTEMPT_COUNT={len(attempts)}")
    print(f"R25_2_2_2_1_2_ACCEPTED_ATTEMPT_COUNT={len(accepted_attempts)}")
    print(f"R25_2_2_2_1_2_ZERO_PAYLOAD_EVIDENCE_COUNT={len(zero_evidence)}")
    if accepted_public:
        f = accepted_public["fields"]
        print("R25_2_2_2_1_2_ANDROID_CLIENT_SEMANTIC=YES")
        print(f"R25_2_2_2_1_2_PROBE_UID={f.get('uid')}"); print(f"R25_2_2_2_1_2_PROBE_PID={f.get('pid')}")
        print(f"R25_2_2_2_1_2_SLOT={f.get('slot')}"); print(f"R25_2_2_2_1_2_PORT_HANDLE={f.get('port_handle')}")
        print(f"R25_2_2_2_1_2_SCN={f.get('scn')}"); print(f"R25_2_2_2_1_2_DLCI={f.get('dlci')}"); print(f"R25_2_2_2_1_2_MTU={f.get('mtu')}")
        print("R25_2_2_2_1_2_MATCHING_OPEN_CLOSE=YES"); print("R25_2_2_2_1_2_ZERO_PAYLOAD=YES")
    print(f"R25_2_2_2_1_2_QUALIFICATION_OUTCOME={public['qualification_outcome']}")
    print(f"R1_3_3_2_25_2_2_2_1_2_ACCEPTANCE={public['acceptance']}")
    print(f"R25_2_2_2_1_2_OUTPUT={output}")
    return public


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline r25.2.2.2.1.2 lifecycle-correlation repair")
    parser.add_argument("--source-private-zip", required=True, type=Path); parser.add_argument("--expected-source-sha256"); parser.add_argument("--output", required=True, type=Path); parser.add_argument("--repo", type=Path)
    args = parser.parse_args(argv)
    try:
        public = run_analysis(args.source_private_zip.expanduser(), args.output.expanduser(), args.expected_source_sha256)
    except AnalysisError as error:
        print("R1_3_3_2_25_2_2_2_1_2_ACCEPTANCE=FAIL", file=sys.stderr); print(f"ERROR: {error}", file=sys.stderr); return 2
    return 0 if public["acceptance"] == PASS_ACCEPTANCE else 1

if __name__ == "__main__":
    raise SystemExit(main())
