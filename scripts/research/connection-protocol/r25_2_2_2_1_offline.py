#!/usr/bin/env python3
"""Offline r25.2.2.2.1 RFCOMM full-zero-payload closure analyzer.

This module consumes an existing private evidence ZIP.  It does not import or
invoke adb, does not open sockets, and does not contact the phone or glasses.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

SCHEMA_PRIVATE = "rokid.r25.2.2.2.1.private-analysis.v1"
SCHEMA_PUBLIC = "rokid.r25.2.2.2.1.public-full-closure.v1"
SCHEMA_STATUS = "rokid.r25.2.runtime-status-summary.v1"
EXPECTED = {"slot": 45, "port_handle": 29, "scn": 3, "dlci": 6, "mtu": 990}
PASS_OUTCOME = "RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE"
PASS_ACCEPTANCE = "PASS_FULL_ZERO_PAYLOAD_CLOSURE"
FAIL_OUTCOME = "RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_NOT_PROVEN"

TEXT_SUFFIXES = {
    ".txt", ".log", ".json", ".jsonl", ".csv", ".xml", ".md", ".out",
}
START_KEYS = (
    "metadata_start_utc", "attempt_start_utc", "action_start_utc",
    "capture_start_utc", "handoff_start_utc", "started_utc", "start_utc",
    "start_time_utc", "started_at_utc", "begin_utc", "begin_time_utc",
)
END_KEYS = (
    "metadata_end_utc", "attempt_end_utc", "action_end_utc",
    "capture_end_utc", "handoff_end_utc", "finished_utc", "end_utc",
    "end_time_utc", "finished_at_utc", "completed_utc", "stop_utc",
)

ISO_RE = re.compile(r"(?P<ts>20\d\d-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:?\d\d)?)")
THREADTIME_RE = re.compile(r"(?<!\d)(?P<ts>\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d{3,6})(?!\d)")
THREADTIME_PID_RE = re.compile(r"^\s*\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d{3,6}\s+(\d+)\s+\d+\s+[VDIWEF]\b")
UUID_RE = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab0-9][0-9a-f]{3}-[0-9a-f]{12})(?![0-9a-f])")
MAC_RE = re.compile(r"(?i)(?<![0-9a-f])([0-9a-f]{2}(?::[0-9a-f]{2}){5})(?![0-9a-f])")
KEY_VALUE_RE = re.compile(r"(?i)\b([a-z][a-z0-9_.-]{1,40})\s*[=:]\s*([^,;\]\[{}()\s]+)")
ATTEMPT_RE = re.compile(r"(?i)\battempt(?:_id|Id| id)?\s*[=:]\s*([A-Za-z0-9_.:-]+)")

CLIENT_PATTERNS = [
    re.compile(r"(?i)\bon_cli_rfc_connect\b"),
    re.compile(r"(?i)\bis[_ -]?server\s*[=:]\s*(?:false|0)\b"),
    re.compile(r"(?i)\b(?:role|side)\s*[=:]\s*client\b"),
    re.compile(r"(?i)\bclient[_ -]?side\s*[=:]\s*true\b"),
    re.compile(r"(?i)\b(?:outgoing|initiator)\s*[=:]\s*true\b"),
    re.compile(r"(?i)\bcreate(?:Insecure)?RfcommSocketToServiceRecord\b"),
    re.compile(r"(?i)\bBluetoothSocket(?:\.connect| connect|.*connectSocketNative)\b"),
    re.compile(r"(?i)\bBTA[_ -]?JvRfcommConnect\b"),
    re.compile(r"(?i)\bbtsock[_ -]?rfc[_ -]?connect\b"),
    re.compile(r"(?i)\bRFCOMM\b.*\bclient\b.*\bconnect"),
]
SERVER_TRUE_RE = re.compile(r"(?i)\bis[_ -]?server\s*[=:]\s*(?:true|1)\b")
RFCOMM_CONTEXT_RE = re.compile(r"(?i)\b(rfcomm|bluetoothsocket|btsock|dlci|scn|port[_ -]?handle)\b")
OPEN_RE = re.compile(r"(?i)(?:\b(?:rfcomm|bluetoothsocket|btsock|port|socket)[^\n]{0,120}\b(?:opened|open success|connected|connect success|port_open|socket_open)\b|\bBTA[_ -]?JV[_ -]?RFCOMM[_ -]?OPEN[_ -]?EVT\b|\bon_(?:srv_)?rfc_connect(?:ed)?\b|\brfc_port_sm_opened\b)")
CLOSE_RE = re.compile(r"(?i)(?:\b(?:rfcomm|bluetoothsocket|btsock|port|socket)[^\n]{0,120}\b(?:closed|close success|disconnected|disconnect|port_close|socket_close)\b|\bBTA[_ -]?JV[_ -]?RFCOMM[_ -]?CLOSE[_ -]?EVT\b|\bon_(?:cli_|srv_)?rfc_close\b|\bBTA[_ -]?JvRfcommClose\b|\brfc_port_sm_closed\b)")
ATTEMPT_START_RE = re.compile(r"(?i)\b(?:attempt|probe)[_ -]?(?:started|start|begin)\b")
ATTEMPT_END_RE = re.compile(r"(?i)\b(?:attempt|probe)[_ -]?(?:finished|complete|completed|end)\b")

FIELD_PATTERNS = {
    "uid": [
        re.compile(r"(?i)\b(?:(?:probe|app)[_ -]?)?uid\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\buid\s+((?:0x)?[0-9a-f]+)\b"),
    ],
    "pid": [
        re.compile(r"(?i)\b(?:probe[_ -]?)?pid\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\bpid\s+((?:0x)?[0-9a-f]+)\b"),
    ],
    "slot": [
        re.compile(r"(?i)\b(?:rfcomm[_ -]?)?slot(?:_id)?\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\bslot(?:\s+id)?\s+((?:0x)?[0-9a-f]+)\b"),
    ],
    "port_handle": [
        re.compile(r"(?i)\bport[_ -]?handle\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\brfc(?:omm)?[_ -]?handle\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\bport[_ -]?handle\s+((?:0x)?[0-9a-f]+)\b"),
    ],
    "scn": [
        re.compile(r"(?i)\bscn\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\bscn\s+((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\bserver[_ -]?channel\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\brfcomm[_ -]?channel\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
    ],
    "dlci": [
        re.compile(r"(?i)\bdlci\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\bdlci\s+((?:0x)?[0-9a-f]+)\b"),
    ],
    "mtu": [
        re.compile(r"(?i)\bmtu\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\bmtu\s+((?:0x)?[0-9a-f]+)\b"),
    ],
    "payload_bytes": [
        re.compile(r"(?i)\b(?:payload(?:_len|_bytes)?|tx[_ -]?bytes|rx[_ -]?bytes|(?:read|write)[_ -]?bytes|bytes[_ -]?(?:sent|written|received|read))\s*[=:]\s*((?:0x)?[0-9a-f]+)\b"),
        re.compile(r"(?i)\bzero[_ -]?payload\s*[=:]\s*(?:true|yes|1)\b"),
    ],
}

ENDPOINT_KV_RE = re.compile(r"(?i)\b(?:endpoint|remote|peer|device|bd[_ -]?addr|address|addr)\s*[=:]\s*([^,;\]\[{}()\s]+)")
UUID_KV_RE = re.compile(r"(?i)\b(?:service[_ -]?)?uuid\s*[=:]\s*([0-9a-f-]{16,40})")


class AnalysisError(RuntimeError):
    pass


def endpoint_parts(value: str) -> Optional[List[str]]:
    parts = value.lower().split(":")
    if len(parts) != 6:
        return None
    if not all(part == "xx" or re.fullmatch(r"[0-9a-f]{2}", part) for part in parts):
        return None
    return parts


def endpoint_values_compatible(values: Sequence[Any]) -> bool:
    unique = [str(value).lower() for value in values]
    mac_like = [endpoint_parts(value) for value in unique]
    concrete = [parts for parts in mac_like if parts and all(part != "xx" for part in parts)]
    if len({tuple(parts) for parts in concrete}) > 1:
        return False
    if concrete:
        raw = concrete[0]
        for parts in mac_like:
            if not parts:
                continue
            for expected, observed in zip(raw, parts):
                if observed != "xx" and observed != expected:
                    return False
    opaque = [value for value, parts in zip(unique, mac_like) if parts is None]
    return len(set(opaque)) <= 1 or bool(concrete or any(parts for parts in mac_like))


def preferred_endpoint(values: Sequence[Any]) -> str:
    strings = [str(value) for value in values]
    concrete = [value for value in strings if endpoint_parts(value) and all(part != "xx" for part in endpoint_parts(value) or [])]
    if concrete:
        return concrete[0].upper()
    mac_like = [value for value in strings if endpoint_parts(value)]
    if mac_like:
        return max(mac_like, key=lambda value: sum(part != "xx" for part in endpoint_parts(value) or []))
    return strings[0]


@dataclass
class SourceLine:
    source: str
    line_number: int
    text: str
    timestamp: dt.datetime
    timestamp_text: str
    event_flags: Tuple[str, ...]
    fields: Dict[str, Any]
    attempt_id: Optional[str]
    fingerprint: str


@dataclass
class Attempt:
    attempt_id: str
    records: List[SourceLine] = field(default_factory=list)
    fields: Dict[str, Any] = field(default_factory=dict)
    conflicts: Dict[str, List[Any]] = field(default_factory=dict)
    client_semantic: bool = False
    open_indices: List[int] = field(default_factory=list)
    close_indices: List[int] = field(default_factory=list)
    zero_payload: bool = False
    endpoint_values: List[str] = field(default_factory=list)
    uuid_values: List[str] = field(default_factory=list)

    def aggregate(self) -> None:
        values: Dict[str, List[Any]] = {}
        for index, record in enumerate(self.records):
            flags = set(record.event_flags)
            if "client_connect" in flags:
                self.client_semantic = True
            if "open" in flags:
                self.open_indices.append(index)
            if "close" in flags:
                self.close_indices.append(index)
            for key, value in record.fields.items():
                if value is None:
                    continue
                values.setdefault(key, []).append(value)
                if key == "endpoint" and value not in self.endpoint_values:
                    self.endpoint_values.append(str(value))
                if key == "uuid" and value not in self.uuid_values:
                    self.uuid_values.append(str(value))
                # Final zero-payload status is computed after all counters are collected.
        payload_observed = [int(value) for value in values.get("payload_bytes", [])]
        self.zero_payload = bool(payload_observed) and all(value == 0 for value in payload_observed)
        for key, observed in values.items():
            unique: List[Any] = []
            for value in observed:
                if value not in unique:
                    unique.append(value)
            if len(unique) == 1:
                self.fields[key] = unique[0]
            elif key == "endpoint" and endpoint_values_compatible(unique):
                self.fields[key] = preferred_endpoint(unique)
                self.fields["endpoint_alias_count"] = len(unique)
            else:
                self.conflicts[key] = unique

    def lifecycle_matched(self) -> bool:
        return bool(self.open_indices and self.close_indices and min(self.open_indices) < max(self.close_indices))

    def tuple_complete(self) -> bool:
        required = ("uuid", "endpoint", "uid", "pid", "slot", "port_handle", "scn", "dlci", "mtu")
        return all(key in self.fields for key in required)

    def expected_values_match(self) -> bool:
        return all(self.fields.get(key) == expected for key, expected in EXPECTED.items())

    def identity_consistent(self) -> bool:
        identity = ("uuid", "endpoint", "uid", "pid")
        return not any(key in self.conflicts for key in identity)

    def accepted(self) -> bool:
        return (
            self.client_semantic
            and self.tuple_complete()
            and self.expected_values_match()
            and self.identity_consistent()
            and self.lifecycle_matched()
            and self.zero_payload
        )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    if text.isdigit():
        return parse_datetime(int(text))
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
        for index, value in enumerate(obj):
            yield from walk_json(value, f"{prefix}[{index}]")


def choose_interval_from_json(data: Any, source: str) -> Optional[Tuple[dt.datetime, dt.datetime, str, str]]:
    flattened = list(walk_json(data))
    starts: List[Tuple[int, str, dt.datetime]] = []
    ends: List[Tuple[int, str, dt.datetime]] = []
    for path, value in flattened:
        key = path.rsplit(".", 1)[-1].lower()
        for priority, candidate in enumerate(START_KEYS):
            if key == candidate:
                parsed = parse_datetime(value)
                if parsed:
                    starts.append((priority, path, parsed))
        for priority, candidate in enumerate(END_KEYS):
            if key == candidate:
                parsed = parse_datetime(value)
                if parsed:
                    ends.append((priority, path, parsed))
    starts.sort(key=lambda item: item[0])
    ends.sort(key=lambda item: item[0])
    for _, start_path, start in starts:
        for _, end_path, end in ends:
            if start <= end:
                return start, end, f"{source}:{start_path}", f"{source}:{end_path}"
    return None


def choose_interval_from_text(text: str, source: str) -> Optional[Tuple[dt.datetime, dt.datetime, str, str]]:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"\s*([A-Za-z0-9_.-]+)\s*[=:]\s*(.*?)\s*$", line)
        if match:
            values[match.group(1).lower()] = match.group(2)
    starts = [(key, parse_datetime(values.get(key))) for key in START_KEYS]
    ends = [(key, parse_datetime(values.get(key))) for key in END_KEYS]
    for start_key, start in starts:
        if not start:
            continue
        for end_key, end in ends:
            if end and start <= end:
                return start, end, f"{source}:{start_key}", f"{source}:{end_key}"
    return None


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
        with zipfile.ZipFile(io.BytesIO(blob), "r") as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                if info.is_dir():
                    continue
                if info.file_size > 128 * 1024 * 1024:
                    continue
                member_data = archive.read(info)
                logical = f"{prefix}{info.filename}"
                suffix = Path(info.filename).suffix.lower()
                basename = Path(info.filename).name.lower()
                if suffix == ".zip" and depth < max_depth:
                    try:
                        yield from recurse(member_data, logical + "!", depth + 1)
                    except zipfile.BadZipFile:
                        pass
                    continue
                if suffix in TEXT_SUFFIXES or any(token in basename for token in ("logcat", "bugreport", "metadata", "rfcomm", "bluetooth", "btsock")):
                    yield logical, member_data

    yield from recurse(data, "", 0)


def discover_interval(path: Path) -> Tuple[dt.datetime, dt.datetime, Dict[str, str]]:
    candidates: List[Tuple[int, dt.datetime, dt.datetime, str, str]] = []
    for source, raw in iter_archive_members(path):
        basename = Path(source.split("!", 1)[0]).name.lower()
        if "metadata" not in basename and "run-info" not in basename and "handoff" not in basename:
            continue
        text = safe_text(raw)
        if text is None:
            continue
        result = None
        if source.lower().endswith((".json", ".jsonl")):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = None
            if data is not None:
                result = choose_interval_from_json(data, source)
        if result is None:
            result = choose_interval_from_text(text, source)
        if result:
            start, end, start_source, end_source = result
            score = 0
            if Path(source).name.lower() == "run-metadata-private.json":
                score -= 100
            if "r25.2.2.2" in source.lower():
                score -= 20
            candidates.append((score, start, end, start_source, end_source))
    if not candidates:
        raise AnalysisError("No exact start/end interval was found in archive metadata")
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    _, start, end, start_source, end_source = candidates[0]
    if end - start > dt.timedelta(hours=2):
        raise AnalysisError("Metadata interval exceeds the two-hour fail-closed bound")
    return start, end, {"start_source": start_source, "end_source": end_source}


def parse_line_timestamp(line: str, year: int, threadtime_offset_minutes: int = 0) -> Tuple[Optional[dt.datetime], Optional[str]]:
    match = ISO_RE.search(line)
    if match:
        parsed = parse_datetime(match.group("ts"))
        return parsed, match.group("ts")
    match = THREADTIME_RE.search(line)
    if match:
        text = match.group("ts")
        try:
            parsed = dt.datetime.strptime(f"{year}-{text}", "%Y-%m-%d %H:%M:%S.%f")
            local = parsed.replace(tzinfo=dt.timezone.utc)
            return local - dt.timedelta(minutes=threadtime_offset_minutes), text
        except ValueError:
            pass
    if line.lstrip().startswith("{"):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            for key in ("timestamp_utc", "ts_utc", "time_utc", "timestamp", "ts", "time", "epoch_ms", "timestamp_ms"):
                if key in data:
                    parsed = parse_datetime(data[key])
                    if parsed:
                        return parsed, str(data[key])
    return None, None


def first_int(text: str, patterns: Sequence[re.Pattern[str]]) -> Optional[int]:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            if match.lastindex:
                try:
                    return int(match.group(1), 0)
                except (TypeError, ValueError):
                    continue
            return 0
    return None


def semantic_text(line: str) -> str:
    # JSONL evidence is common; quote removal lets the same bounded regexes
    # recognize keys such as "is_server":false and "slot":45.
    return line.replace("\"", "").replace("\'", "")


def extract_fields(line: str) -> Dict[str, Any]:
    line = semantic_text(line)
    fields: Dict[str, Any] = {}
    uuid_match = UUID_KV_RE.search(line) or UUID_RE.search(line)
    if uuid_match:
        fields["uuid"] = uuid_match.group(1).lower()
    endpoint_match = ENDPOINT_KV_RE.search(line)
    if endpoint_match:
        fields["endpoint"] = endpoint_match.group(1)
    else:
        mac_match = MAC_RE.search(line)
        if mac_match:
            fields["endpoint"] = mac_match.group(1).upper()
    for key, patterns in FIELD_PATTERNS.items():
        value = first_int(line, patterns)
        if value is not None:
            fields[key] = value
    pid_match = THREADTIME_PID_RE.search(line)
    if pid_match:
        fields["source_pid"] = int(pid_match.group(1))
        if "pid" not in fields and re.search(r"(?i)(channelprobe|org\.aimindseye\.rokid|evidencelogger|r25[_ -]?probe)", line):
            fields["pid"] = int(pid_match.group(1))
    if "uid" in fields and int(fields["uid"]) >= 100000:
        fields["android_uid_full"] = int(fields["uid"])
        fields["uid"] = int(fields["uid"]) % 100000
    if "mtu" not in fields and re.search(r"(?i)\bbta_jv_port_data_co_cback\b", line):
        length_match = re.search(r"(?i)\blen\s*[=:]\s*((?:0x)?[0-9a-f]+)\b", line)
        if length_match:
            fields["mtu"] = int(length_match.group(1), 0)
    if re.search(r"(?i)\bzero[_ -]?payload\s*[=:]\s*(?:true|yes|1)\b", line):
        fields["payload_bytes"] = 0
    return fields


def classify_flags(line: str) -> Tuple[str, ...]:
    line = semantic_text(line)
    flags: List[str] = []
    has_rfcomm_context = bool(RFCOMM_CONTEXT_RE.search(line))
    client = any(pattern.search(line) for pattern in CLIENT_PATTERNS)
    if client and not SERVER_TRUE_RE.search(line) and (has_rfcomm_context or "on_cli_rfc_connect" in line.lower()):
        flags.append("client_connect")
    if OPEN_RE.search(line) and not CLOSE_RE.search(line):
        flags.append("open")
    if CLOSE_RE.search(line):
        flags.append("close")
    if ATTEMPT_START_RE.search(line):
        flags.append("attempt_start")
    if ATTEMPT_END_RE.search(line):
        flags.append("attempt_end")
    return tuple(sorted(set(flags)))


def canonical_fingerprint(timestamp: dt.datetime, flags: Sequence[str], fields: Dict[str, Any], line: str) -> str:
    semantic = {
        "timestamp_ms": int(timestamp.timestamp() * 1000),
        "flags": sorted(flags),
        "fields": {key: fields[key] for key in sorted(fields)},
    }
    if not flags and not fields:
        normalized = re.sub(r"^.*?\b(?:[VDIWEF])/[^:]+:\s*", "", line.strip())
        normalized = re.sub(r"\s+", " ", normalized)
        semantic["text"] = normalized
    return sha256_bytes(json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def infer_threadtime_offset(path: Path, start: dt.datetime, end: dt.datetime) -> int:
    naive_times: List[dt.datetime] = []
    for _, raw in iter_archive_members(path):
        text = safe_text(raw)
        if text is None:
            continue
        for line in text.splitlines():
            if ISO_RE.search(line):
                continue
            match = THREADTIME_RE.search(line)
            if not match:
                continue
            if not extract_fields(line) and not classify_flags(line):
                continue
            try:
                parsed = dt.datetime.strptime(f"{start.year}-{match.group('ts')}", "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                continue
            naive_times.append(parsed.replace(tzinfo=dt.timezone.utc))
    if not naive_times:
        return 0
    scores: List[Tuple[int, int]] = []
    for offset in range(-14 * 60, 14 * 60 + 1, 15):
        count = sum(1 for value in naive_times if start <= value - dt.timedelta(minutes=offset) <= end)
        scores.append((count, offset))
    best_count = max(count for count, _ in scores)
    if best_count == 0:
        return 0
    best_offsets = [offset for count, offset in scores if count == best_count]
    return min(best_offsets, key=lambda value: (abs(value), value))


def collect_records(path: Path, start: dt.datetime, end: dt.datetime) -> Tuple[List[SourceLine], Dict[str, int]]:
    records: List[SourceLine] = []
    threadtime_offset_minutes = infer_threadtime_offset(path, start, end)
    stats = {
        "raw_timestamped_lines": 0,
        "outside_interval_lines": 0,
        "inside_interval_lines": 0,
        "semantic_lines": 0,
        "duplicate_semantic_lines": 0,
        "threadtime_utc_offset_minutes": threadtime_offset_minutes,
    }
    seen: Dict[str, SourceLine] = {}
    for source, raw in iter_archive_members(path):
        text = safe_text(raw)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            timestamp, timestamp_text = parse_line_timestamp(line, start.year, threadtime_offset_minutes)
            if timestamp is None:
                continue
            stats["raw_timestamped_lines"] += 1
            if not (start <= timestamp <= end):
                stats["outside_interval_lines"] += 1
                continue
            stats["inside_interval_lines"] += 1
            fields = extract_fields(line)
            flags = classify_flags(line)
            if not fields and not flags:
                continue
            stats["semantic_lines"] += 1
            attempt_match = ATTEMPT_RE.search(semantic_text(line))
            attempt_id = attempt_match.group(1) if attempt_match else None
            fingerprint = canonical_fingerprint(timestamp, flags, fields, line)
            record = SourceLine(
                source=source,
                line_number=line_number,
                text=line,
                timestamp=timestamp,
                timestamp_text=timestamp_text or "",
                event_flags=flags,
                fields=fields,
                attempt_id=attempt_id,
                fingerprint=fingerprint,
            )
            if fingerprint in seen:
                stats["duplicate_semantic_lines"] += 1
                continue
            seen[fingerprint] = record
            records.append(record)
    records.sort(key=lambda item: (item.timestamp, item.source, item.line_number))
    return records, stats


def group_attempts(records: Sequence[SourceLine]) -> List[Attempt]:
    explicit: Dict[str, Attempt] = {}
    for record in records:
        if record.attempt_id:
            explicit.setdefault(record.attempt_id, Attempt(record.attempt_id)).records.append(record)

    explicit_attempts = list(explicit.values())
    for attempt in explicit_attempts:
        attempt.records.sort(key=lambda item: (item.timestamp, item.source, item.line_number))
    explicit_attempts.sort(key=lambda item: item.records[0].timestamp)

    assigned = {id(record) for attempt in explicit_attempts for record in attempt.records}
    # Native Android/bugreport records often omit the app's attempt ID.  Absorb
    # only unassigned records from the same bounded client-connect lifecycle.
    for index, attempt in enumerate(explicit_attempts):
        client_records = [record for record in attempt.records if "client_connect" in record.event_flags]
        anchor = client_records[0].timestamp if client_records else attempt.records[0].timestamp
        next_anchor = None
        if index + 1 < len(explicit_attempts):
            next_clients = [record for record in explicit_attempts[index + 1].records if "client_connect" in record.event_flags]
            next_anchor = next_clients[0].timestamp if next_clients else explicit_attempts[index + 1].records[0].timestamp
        window_start = anchor - dt.timedelta(seconds=10)
        window_end = (next_anchor - dt.timedelta(microseconds=1)) if next_anchor else (anchor + dt.timedelta(seconds=60))
        candidates = [
            record for record in records
            if id(record) not in assigned
            and record.attempt_id is None
            and window_start <= record.timestamp <= window_end
        ]
        open_seen = any("open" in record.event_flags for record in attempt.records if record.timestamp >= anchor)
        for record in candidates:
            attempt.records.append(record)
            assigned.add(id(record))
            if record.timestamp >= anchor:
                open_seen = open_seen or "open" in record.event_flags
                if open_seen and "close" in record.event_flags:
                    break
        attempt.records.sort(key=lambda item: (item.timestamp, item.source, item.line_number))
        attempt.aggregate()

    attempts: List[Attempt] = list(explicit_attempts)
    connect_indices = [
        i for i, record in enumerate(records)
        if "client_connect" in record.event_flags and id(record) not in assigned
    ]
    for ordinal, connect_index in enumerate(connect_indices, 1):
        next_connect = connect_indices[ordinal] if ordinal < len(connect_indices) else len(records)
        connect_time = records[connect_index].timestamp
        start_index = connect_index
        while start_index > 0 and records[start_index - 1].timestamp >= connect_time - dt.timedelta(seconds=10):
            if "client_connect" in records[start_index - 1].event_flags:
                break
            start_index -= 1
        end_index = next_connect
        open_seen = False
        for record_index in range(connect_index, next_connect):
            flags = set(records[record_index].event_flags)
            open_seen = open_seen or "open" in flags
            if open_seen and "close" in flags:
                end_index = record_index + 1
                break
            if records[record_index].timestamp > connect_time + dt.timedelta(seconds=60):
                end_index = record_index
                break
        attempt_records = [record for record in records[start_index:end_index] if id(record) not in assigned]
        if attempt_records:
            attempt = Attempt(f"inferred-{ordinal}", attempt_records)
            attempt.aggregate()
            attempts.append(attempt)
            assigned.update(id(record) for record in attempt_records)

    attempts.sort(key=lambda item: item.records[0].timestamp if item.records else dt.datetime.max.replace(tzinfo=dt.timezone.utc))
    return attempts


def evidence_ref(record: SourceLine, include_text: bool) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "source": record.source,
        "line": record.line_number,
        "timestamp_utc": record.timestamp.isoformat().replace("+00:00", "Z"),
        "flags": list(record.event_flags),
        "fields": record.fields,
        "fingerprint_sha256": record.fingerprint,
    }
    if include_text:
        result["text"] = record.text
    return result


def endpoint_token(endpoint: str) -> str:
    return "endpoint-sha256:" + sha256_bytes(endpoint.encode("utf-8"))[:16]


def uuid_token(uuid: str) -> str:
    return "uuid-sha256:" + sha256_bytes(uuid.encode("utf-8"))[:16]


def attempt_private(attempt: Attempt) -> Dict[str, Any]:
    return {
        "attempt_id": attempt.attempt_id,
        "accepted": attempt.accepted(),
        "client_semantic": attempt.client_semantic,
        "lifecycle_matched": attempt.lifecycle_matched(),
        "zero_payload": attempt.zero_payload,
        "tuple_complete": attempt.tuple_complete(),
        "expected_values_match": attempt.expected_values_match(),
        "identity_consistent": attempt.identity_consistent(),
        "fields": attempt.fields,
        "conflicts": attempt.conflicts,
        "records": [evidence_ref(record, True) for record in attempt.records],
    }


def attempt_public(attempt: Attempt) -> Dict[str, Any]:
    public_keys = {"uuid", "endpoint", "uid", "pid", "slot", "port_handle", "scn", "dlci", "mtu", "payload_bytes"}
    fields = {key: value for key, value in attempt.fields.items() if key in public_keys}
    if "endpoint" in fields:
        fields["endpoint"] = endpoint_token(str(fields["endpoint"]))
    if "uuid" in fields:
        fields["uuid"] = uuid_token(str(fields["uuid"]))
    conflicts: Dict[str, List[Any]] = {}
    for key, values in attempt.conflicts.items():
        if key == "endpoint":
            conflicts[key] = [endpoint_token(str(value)) for value in values]
        elif key == "uuid":
            conflicts[key] = [uuid_token(str(value)) for value in values]
        else:
            conflicts[key] = values
    return {
        "attempt_id": attempt.attempt_id,
        "accepted": attempt.accepted(),
        "client_semantic": attempt.client_semantic,
        "lifecycle_matched": attempt.lifecycle_matched(),
        "zero_payload": attempt.zero_payload,
        "tuple_complete": attempt.tuple_complete(),
        "expected_values_match": attempt.expected_values_match(),
        "identity_consistent": attempt.identity_consistent(),
        "fields": fields,
        "conflicts": conflicts,
        "evidence_fingerprints": [record.fingerprint for record in attempt.records],
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def manifest(root: Path, destination: Path) -> None:
    lines: List[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path != destination:
            lines.append(f"{sha256_file(path)}  {path.relative_to(root)}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_zip(root: Path, destination: Path, arc_root: Optional[str] = None) -> None:
    if destination.exists():
        destination.unlink()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            arcname = str(Path(arc_root) / relative) if arc_root else str(relative)
            info = zipfile.ZipInfo(arcname, date_time=(2026, 7, 27, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def privacy_gate(publication: Path, raw_values: Sequence[str]) -> List[str]:
    violations: List[str] = []
    for path in publication.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        for value in raw_values:
            if value and value.encode("utf-8") in data:
                violations.append(f"{path.name}:raw-value")
        text = safe_text(data) or ""
        if MAC_RE.search(text):
            violations.append(f"{path.name}:raw-mac")
        if UUID_RE.search(text):
            violations.append(f"{path.name}:raw-uuid")
        if re.search(r"/Users/[^/\s]+|[A-Za-z]:\\Users\\", text):
            violations.append(f"{path.name}:absolute-user-path")
    return sorted(set(violations))


def render_markdown(public: Dict[str, Any]) -> str:
    accepted = public["acceptance"] == PASS_ACCEPTANCE
    accepted_attempt = public.get("accepted_attempt") or {}
    fields = accepted_attempt.get("fields", {})
    return f"""# r1.3.3.2.25.2.2.2.1 — Android RFCOMM Client Full Zero-Payload Closure

## Disposition

**{public['acceptance']}**

The existing private archive was analyzed offline. No phone or glasses contact
is performed by this repair.

## Bounded result

- Client-side RFCOMM semantic recognized: **{'YES' if accepted_attempt.get('client_semantic') else 'NO'}**
- Same-attempt identity and parameter tuple complete: **{'YES' if accepted_attempt.get('tuple_complete') else 'NO'}**
- Matching open then close records: **{'YES' if accepted_attempt.get('lifecycle_matched') else 'NO'}**
- Zero payload: **{'YES' if accepted_attempt.get('zero_payload') else 'NO'}**
- Promoted full closure: **{'YES' if accepted else 'NO'}**

## Qualified runtime tuple

| Field | Value |
|---|---:|
| Endpoint | {fields.get('endpoint', 'UNRESOLVED')} |
| UUID | {fields.get('uuid', 'UNRESOLVED')} |
| Probe UID | {fields.get('uid', 'UNRESOLVED')} |
| Probe PID | {fields.get('pid', 'UNRESOLVED')} |
| Slot | {fields.get('slot', 'UNRESOLVED')} |
| Port handle | {fields.get('port_handle', 'UNRESOLVED')} |
| SCN | {fields.get('scn', 'UNRESOLVED')} |
| DLCI | {fields.get('dlci', 'UNRESOLVED')} |
| MTU | {fields.get('mtu', 'UNRESOLVED')} |

## Evidence controls

Only timestamped records inside the exact metadata start/end interval were
eligible. Overlapping semantic records copied between logcat and bugreport were
deduplicated before attempt correlation. Values from different attempts were
not merged.
"""


def run_analysis(source_zip: Path, output: Path, expected_source_sha256: Optional[str]) -> Dict[str, Any]:
    if not source_zip.is_file():
        raise AnalysisError(f"Source private archive not found: {source_zip}")
    source_sha = sha256_file(source_zip)
    if expected_source_sha256 and source_sha.lower() != expected_source_sha256.lower():
        raise AnalysisError(
            f"Source archive SHA-256 mismatch: expected {expected_source_sha256}, observed {source_sha}"
        )
    start, end, interval_sources = discover_interval(source_zip)
    records, stats = collect_records(source_zip, start, end)
    attempts = group_attempts(records)
    accepted_attempts = [attempt for attempt in attempts if attempt.accepted()]
    accepted = len(accepted_attempts) == 1
    ambiguity = len(accepted_attempts) > 1
    if ambiguity:
        accepted = False

    output.mkdir(parents=True, exist_ok=False)
    analysis_dir = output / "analysis"
    publication_dir = output / "publication"
    analysis_dir.mkdir()
    publication_dir.mkdir()

    private = {
        "schema": SCHEMA_PRIVATE,
        "source_private_archive": {
            "filename": source_zip.name,
            "sha256": source_sha,
        },
        "metadata_interval": {
            "start_utc": start.isoformat().replace("+00:00", "Z"),
            "end_utc": end.isoformat().replace("+00:00", "Z"),
            **interval_sources,
        },
        "selection_stats": stats,
        "attempt_count": len(attempts),
        "accepted_attempt_count": len(accepted_attempts),
        "ambiguity_fail_closed": ambiguity,
        "qualification_outcome": PASS_OUTCOME if accepted else FAIL_OUTCOME,
        "acceptance": PASS_ACCEPTANCE if accepted else "FAIL_FULL_ZERO_PAYLOAD_CLOSURE",
        "attempts": [attempt_private(attempt) for attempt in attempts],
    }
    write_json(analysis_dir / "r25.2.2.2.1-private-analysis.json", private)

    accepted_public = attempt_public(accepted_attempts[0]) if accepted else None
    public = {
        "schema": SCHEMA_PUBLIC,
        "source_private_archive_sha256": source_sha,
        "metadata_interval": {
            "start_utc": start.isoformat().replace("+00:00", "Z"),
            "end_utc": end.isoformat().replace("+00:00", "Z"),
        },
        "evidence_controls": {
            "metadata_interval_enforced": True,
            "overlapping_logcat_bugreport_deduplicated": True,
            "same_attempt_correlation_required": True,
            "matching_open_close_required": True,
            "offline_only": True,
        },
        "selection_stats": stats,
        "attempt_count": len(attempts),
        "accepted_attempt_count": len(accepted_attempts),
        "qualification_outcome": PASS_OUTCOME if accepted else FAIL_OUTCOME,
        "acceptance": PASS_ACCEPTANCE if accepted else "FAIL_FULL_ZERO_PAYLOAD_CLOSURE",
        "accepted_attempt": accepted_public,
        "expected_runtime_tuple": EXPECTED,
    }
    write_json(publication_dir / "r25.2.2.2.1-full-zero-payload-closure.json", public)
    write_text(publication_dir / "r25.2.2.2.1-full-zero-payload-closure.md", render_markdown(public))
    status = {
        "schema": SCHEMA_STATUS,
        "release": "r1.3.3.2.25.2.2.2.1",
        "acceptance": public["acceptance"],
        "qualification_outcome": public["qualification_outcome"],
        "rfcomm_client_semantic_confirmed": bool(accepted_public and accepted_public["client_semantic"]),
        "same_attempt_runtime_tuple_confirmed": bool(accepted_public and accepted_public["tuple_complete"]),
        "matching_open_close_confirmed": bool(accepted_public and accepted_public["lifecycle_matched"]),
        "zero_payload_confirmed": bool(accepted_public and accepted_public["zero_payload"]),
        "offline_regeneration": True,
    }
    write_json(publication_dir / "runtime-status-summary.json", status)
    write_text(publication_dir / "methodology.md", """# Methodology

1. Verify the existing private archive hash when supplied.
2. Read the exact start and end timestamps from archive metadata.
3. Admit only timestamped records inside that closed interval.
4. Recognize Android RFCOMM client semantics, including `on_cli_rfc_connect`,
   `is_server=false`, client-role, outgoing/initiator, and BluetoothSocket forms.
5. Deduplicate semantically identical records copied between logcat and bugreport.
6. Group evidence by explicit attempt ID or one inferred client-connect lifecycle.
7. Require UUID, endpoint, UID, PID, slot 45, handle 29, SCN 3, DLCI 6, MTU 990,
   ordered open/close records, and zero payload in one attempt.
8. Fail closed on missing, conflicting, cross-attempt, or multiply qualifying evidence.
""")
    write_text(publication_dir / "limitations.md", """# Limitations

This repair promotes only the bounded connection-only zero-payload lifecycle.
It does not claim application payload semantics, bidirectional data transfer,
stock Hi Rokid equivalence beyond the observed RFCOMM runtime tuple, or behavior
outside the metadata interval. Raw endpoint and runtime UUID values remain in
the private analysis only and are replaced by SHA-256-derived tokens publicly.
""")

    raw_values: List[str] = []
    for attempt in attempts:
        raw_values.extend(attempt.endpoint_values)
        raw_values.extend(attempt.uuid_values)
    violations = privacy_gate(publication_dir, raw_values)
    if violations:
        raise AnalysisError("Sanitized publication privacy gate failed: " + ", ".join(violations))

    manifest(publication_dir, publication_dir / "evidence-hashes.txt")
    manifest(output, output / "SHA256SUMS-private.txt")
    make_zip(publication_dir, output.with_name(output.name + "-sanitized-publication.zip"), arc_root=publication_dir.name)
    make_zip(output, output.with_name(output.name + "-private-analysis.zip"), arc_root=output.name)

    print(f"R25_2_2_2_1_SOURCE_PRIVATE_ZIP_SHA256={source_sha}")
    print(f"R25_2_2_2_1_METADATA_INTERVAL_START={start.isoformat().replace('+00:00', 'Z')}")
    print(f"R25_2_2_2_1_METADATA_INTERVAL_END={end.isoformat().replace('+00:00', 'Z')}")
    print(f"R25_2_2_2_1_INTERVAL_FILTER=PASS")
    print(f"R25_2_2_2_1_DEDUPLICATION=PASS")
    print(f"R25_2_2_2_1_ATTEMPT_COUNT={len(attempts)}")
    print(f"R25_2_2_2_1_ACCEPTED_ATTEMPT_COUNT={len(accepted_attempts)}")
    if accepted_public:
        fields = accepted_public["fields"]
        print("R25_2_2_2_1_ANDROID_CLIENT_SEMANTIC=YES")
        print(f"R25_2_2_2_1_SLOT={fields.get('slot')}")
        print(f"R25_2_2_2_1_PORT_HANDLE={fields.get('port_handle')}")
        print(f"R25_2_2_2_1_SCN={fields.get('scn')}")
        print(f"R25_2_2_2_1_DLCI={fields.get('dlci')}")
        print(f"R25_2_2_2_1_MTU={fields.get('mtu')}")
        print("R25_2_2_2_1_MATCHING_OPEN_CLOSE=YES")
        print("R25_2_2_2_1_ZERO_PAYLOAD=YES")
    print(f"R25_2_2_2_1_QUALIFICATION_OUTCOME={public['qualification_outcome']}")
    print(f"R1_3_3_2_25_2_2_2_1_ACCEPTANCE={public['acceptance']}")
    print(f"R25_2_2_2_1_OUTPUT={output}")
    return public


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline r25.2.2.2.1 full zero-payload closure promotion")
    parser.add_argument("--source-private-zip", required=True, type=Path)
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo", type=Path, help="Accepted for repository-runner compatibility; no device operation is performed")
    args = parser.parse_args(argv)
    try:
        public = run_analysis(args.source_private_zip.expanduser(), args.output.expanduser(), args.expected_source_sha256)
    except AnalysisError as error:
        print(f"R1_3_3_2_25_2_2_2_1_ACCEPTANCE=FAIL", file=sys.stderr)
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0 if public["acceptance"] == PASS_ACCEPTANCE else 1


if __name__ == "__main__":
    raise SystemExit(main())
