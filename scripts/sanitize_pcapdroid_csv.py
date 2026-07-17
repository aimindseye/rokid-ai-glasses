#!/usr/bin/env python3
"""Aggregate PCAPdroid CSV data without IPs, UIDs, or ephemeral ports."""
from __future__ import annotations

import argparse
import csv
import ipaddress
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

REDACTED = "[REDACTED]"
MAC_RE = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")

@dataclass
class Summary:
    app: str
    package: str
    host: str
    protocol: str
    status: str
    destination_port: str
    connections: int
    bytes_sent: int
    bytes_received: int
    packets_sent: int
    packets_received: int
    first_seen: str
    last_seen: str


def sanitize_info(value: str) -> str:
    value = value.strip()
    try:
        ipaddress.ip_address(value)
        return REDACTED
    except ValueError:
        pass
    return MAC_RE.sub(REDACTED, value)


def number(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def load(path: Path) -> list[Summary]:
    items: OrderedDict[tuple[str, ...], Summary] = OrderedDict()
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle):
            host = sanitize_info(row.get("Info", ""))
            key = (
                row.get("App", ""), row.get("PackageName", ""), host,
                row.get("Proto", ""), row.get("Status", ""), row.get("DstPort", ""),
            )
            if key not in items:
                items[key] = Summary(
                    app=key[0], package=key[1], host=key[2], protocol=key[3], status=key[4],
                    destination_port=key[5], connections=1,
                    bytes_sent=number(row.get("BytesSent", "")),
                    bytes_received=number(row.get("BytesRcvd", "")),
                    packets_sent=number(row.get("PktsSent", "")),
                    packets_received=number(row.get("PktsRcvd", "")),
                    first_seen=row.get("FirstSeen", ""), last_seen=row.get("LastSeen", ""),
                )
            else:
                s = items[key]
                s.connections += 1
                s.bytes_sent += number(row.get("BytesSent", ""))
                s.bytes_received += number(row.get("BytesRcvd", ""))
                s.packets_sent += number(row.get("PktsSent", ""))
                s.packets_received += number(row.get("PktsRcvd", ""))
                current_first = row.get("FirstSeen", "")
                current_last = row.get("LastSeen", "")
                if current_first and (not s.first_seen or current_first < s.first_seen):
                    s.first_seen = current_first
                if current_last and (not s.last_seen or current_last > s.last_seen):
                    s.last_seen = current_last
    return list(items.values())


def write_csv(items: list[Summary], path: Path) -> None:
    fields = [
        "App", "PackageName", "Host", "Protocol", "Status", "DestinationPort",
        "Connections", "BytesSent", "BytesReceived", "PacketsSent", "PacketsReceived",
        "FirstSeen", "LastSeen",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(fields)
        for s in items:
            writer.writerow([
                s.app, s.package, s.host, s.protocol, s.status, s.destination_port,
                s.connections, s.bytes_sent, s.bytes_received, s.packets_sent,
                s.packets_received, s.first_seen, s.last_seen,
            ])


def write_markdown(items: list[Summary], path: Path) -> None:
    lines = [
        "# Test 03b — Sanitized PCAPdroid Connection Summary", "",
        "Source IPs, destination IPs, UIDs, and source ports are omitted.", "",
        "| Host | Protocol | Status | Connections | Sent | Received |",
        "|---|---|---|---:|---:|---:|",
    ]
    for s in items:
        lines.append(
            f"| `{s.host}` | `{s.protocol}` | `{s.status}` | {s.connections} | "
            f"{s.bytes_sent} B | {s.bytes_received} B |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    args = parser.parse_args()
    items = load(args.input)
    if not items:
        raise SystemExit("No PCAPdroid rows were parsed")
    write_csv(items, args.csv)
    write_markdown(items, args.markdown)
    print(f"Sanitized connection groups: {len(items)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
