#!/usr/bin/env python3
"""Summarize decoded WebSocket occurrences by marker window."""

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
    parser.add_argument("--timeline", required=True, type=Path)
    parser.add_argument("--safe-summary", required=True, type=Path)
    args = parser.parse_args()

    with args.timeline.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    markers = {row["marker"]: float(row["epoch"]) for row in rows}
    required = ["ACTION_START", "ACTION_COMPLETE", "RESPONSE_START", "RESPONSE_COMPLETE", "END"]
    missing = [name for name in required if name not in markers]
    if missing:
        raise SystemExit("ERROR: missing markers: " + ", ".join(missing))

    def window(epoch: float) -> str:
        if epoch < markers["ACTION_START"]:
            return "pre_action"
        if epoch <= markers["ACTION_COMPLETE"]:
            return "invocation_and_speech"
        if epoch < markers["RESPONSE_START"]:
            return "post_speech_pre_response"
        if epoch <= markers["RESPONSE_COMPLETE"]:
            return "observable_response"
        if epoch <= markers["END"]:
            return "post_response_idle"
        return "after_end"

    groups: dict[str, dict[str, int]] = {}
    for line in args.websocket_tsv.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split("\t") + [""] * 10
        _frame, epoch_text, _stream, _src, src_port, _dst, dst_port, opcode_field, _length, payload_field = fields[:10]
        try:
            epoch = float(epoch_text)
        except ValueError:
            continue
        direction = "client_to_server" if dst_port == "443" else "server_to_client" if src_port == "443" else "unknown"
        payload_values = [value.strip() for value in payload_field.split("|") if value.strip()]
        opcode_values = [value.strip() for value in opcode_field.split("|") if value.strip()]
        for occurrence, payload_hex in enumerate(payload_values, start=1):
            payload = decode_hex(payload_hex)
            if payload is None:
                continue
            opcode = opcode_values[occurrence - 1] if occurrence - 1 < len(opcode_values) else opcode_values[0] if opcode_values else "unknown"
            key = f"{window(epoch)}|{direction}|{opcode}"
            group = groups.setdefault(key, {"records": 0, "payload_bytes": 0})
            group["records"] += 1
            group["payload_bytes"] += len(payload)

    report = {
        "schema": "rokid.voice-canary.traffic-summary.v1",
        "groups": groups,
        "marker_durations_seconds": {
            "action": markers["ACTION_COMPLETE"] - markers["ACTION_START"],
            "pre_response": markers["RESPONSE_START"] - markers["ACTION_COMPLETE"],
            "observable_response": markers["RESPONSE_COMPLETE"] - markers["RESPONSE_START"],
            "post_response_idle": markers["END"] - markers["RESPONSE_COMPLETE"],
        },
    }
    args.safe_summary.parent.mkdir(parents=True, exist_ok=True)
    args.safe_summary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("WebSocket traffic summary: PASS")
    print(args.safe_summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
