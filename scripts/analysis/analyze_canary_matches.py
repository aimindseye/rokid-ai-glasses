#!/usr/bin/env python3
"""Search an occurrence-aware WebSocket TSV for allowlisted controlled phrases."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


def decode_hex(value: str) -> bytes | None:
    normalized = "".join(ch for ch in value if ch in "0123456789abcdefABCDEF")
    if not normalized or len(normalized) % 2:
        return None
    try:
        return bytes.fromhex(normalized)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--websocket-tsv", required=True, type=Path)
    parser.add_argument("--terms-json", required=True, type=Path)
    parser.add_argument("--private-matches", required=True, type=Path)
    parser.add_argument("--safe-summary", required=True, type=Path)
    args = parser.parse_args()

    terms_raw = json.loads(args.terms_json.read_text(encoding="utf-8"))
    if not isinstance(terms_raw, dict) or not terms_raw:
        raise SystemExit("ERROR: terms JSON must be a non-empty object")
    terms = {str(label): str(value).encode("utf-8").lower() for label, value in terms_raw.items()}

    matches: list[dict[str, object]] = []
    total_records = 0
    totals = {
        "client_to_server": {"records": 0, "payload_bytes": 0},
        "server_to_client": {"records": 0, "payload_bytes": 0},
        "unknown": {"records": 0, "payload_bytes": 0},
    }

    for line in args.websocket_tsv.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split("\t") + [""] * 10
        frame, epoch, stream, _src, src_port, _dst, dst_port, opcode_field, _length, payload_field = fields[:10]
        payload_values = [value.strip() for value in payload_field.split("|") if value.strip()]
        opcode_values = [value.strip() for value in opcode_field.split("|") if value.strip()]
        direction = "client_to_server" if dst_port == "443" else "server_to_client" if src_port == "443" else "unknown"

        for occurrence, payload_hex in enumerate(payload_values, start=1):
            payload = decode_hex(payload_hex)
            if payload is None:
                continue
            total_records += 1
            totals[direction]["records"] += 1
            totals[direction]["payload_bytes"] += len(payload)
            lowered = payload.lower()
            found = sorted(label for label, term in terms.items() if term in lowered)
            if not found:
                continue
            opcode = opcode_values[occurrence - 1] if occurrence - 1 < len(opcode_values) else opcode_values[0] if opcode_values else "unknown"
            matches.append({
                "frame": frame,
                "epoch": epoch,
                "tcp_stream": stream,
                "direction": direction,
                "opcode": opcode,
                "occurrence": occurrence,
                "decoded_bytes": len(payload),
                "matched_terms": ",".join(found),
            })

    args.private_matches.parent.mkdir(parents=True, exist_ok=True)
    with args.private_matches.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "frame", "epoch", "tcp_stream", "direction", "opcode",
            "occurrence", "decoded_bytes", "matched_terms"
        ], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(matches)

    group_counts: dict[str, int] = {}
    for row in matches:
        key = f"{row['direction']}|{row['matched_terms']}"
        group_counts[key] = group_counts.get(key, 0) + 1

    summary = {
        "schema": "rokid.voice-canary.safe-summary.v1",
        "websocket_record_count": total_records,
        "match_count": len(matches),
        "match_groups": group_counts,
        "traffic_totals": totals,
    }
    args.safe_summary.parent.mkdir(parents=True, exist_ok=True)
    args.safe_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Canary match analysis: PASS")
    print(args.safe_summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
