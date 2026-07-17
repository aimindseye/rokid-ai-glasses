#!/usr/bin/env python3
"""Sanitize an eight-field tshark HTTP request export for public use."""
from __future__ import annotations

import argparse
import csv
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit

REDACTED = "[REDACTED]"
UUID_RE = re.compile(r"(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
HEX_RE = re.compile(r"(?i)^[0-9a-f]{16,}$")
LONG_ID_RE = re.compile(r"^[A-Za-z0-9_-]{24,}$")
IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
MAC_RE = re.compile(r"(?i)^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$")

@dataclass
class Record:
    method: str
    host: str
    path: str
    count: int
    first_seen: str
    last_seen: str


def sanitize_segment(segment: str) -> str:
    if UUID_RE.fullmatch(segment) or HEX_RE.fullmatch(segment) or LONG_ID_RE.fullmatch(segment):
        return REDACTED
    return segment


def sanitize_host(host: str) -> str:
    host = host.strip().lower()
    if IPV4_RE.fullmatch(host) or MAC_RE.fullmatch(host):
        return REDACTED
    return host


def sanitize_path(raw: str) -> str:
    raw = raw.strip() or "/"
    parts = urlsplit(raw)
    path = "/".join(sanitize_segment(seg) for seg in parts.path.split("/"))
    if not path.startswith("/"):
        path = "/" + path
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    if not pairs:
        return path
    query = "&".join(f"{quote(name, safe='[]_.-')}={REDACTED}" for name, _ in pairs)
    return f"{path}?{query}"


def load_records(path: Path) -> list[Record]:
    aggregated: OrderedDict[tuple[str, str, str], Record] = OrderedDict()
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if not line.strip():
                continue
            cols = line.split("\t")
            cols += [""] * (8 - len(cols))
            frame, timestamp, h1_method, h1_host, h1_path, h2_method, h2_host, h2_path = cols[:8]
            method = (h1_method or h2_method).strip().upper()
            host = sanitize_host(h1_host or h2_host)
            request_path = sanitize_path(h1_path or h2_path)
            if not method or not host:
                continue
            key = (method, host, request_path)
            if key not in aggregated:
                aggregated[key] = Record(method, host, request_path, 1, timestamp, timestamp)
            else:
                rec = aggregated[key]
                rec.count += 1
                rec.last_seen = timestamp
    return list(aggregated.values())


def write_tsv(records: list[Record], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["method", "host", "sanitized_path", "count", "first_seen", "last_seen"])
        for r in records:
            writer.writerow([r.method, r.host, r.path, r.count, r.first_seen, r.last_seen])


def write_markdown(records: list[Record], path: Path) -> None:
    lines = [
        "# Test 03b — Sanitized HTTP Request Paths",
        "",
        "All query values and identifier-like path segments are redacted.",
        "",
        "| Method | Host | Sanitized path | Count |",
        "|---|---|---|---:|",
    ]
    for r in records:
        safe_path = r.path.replace("|", "\\|")
        lines.append(f"| `{r.method}` | `{r.host}` | `{safe_path}` | {r.count} |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--tsv", required=True, type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    args = parser.parse_args()
    records = load_records(args.input)
    if not records:
        raise SystemExit("No HTTP request records were parsed")
    write_tsv(records, args.tsv)
    write_markdown(records, args.markdown)
    print(f"Sanitized HTTP records: {len(records)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
