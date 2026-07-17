#!/usr/bin/env python3
"""Compare two sanitized canary JSON summaries without reading raw evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "rokid.voice-canary.safe-summary.v1":
        raise SystemExit(f"ERROR: unsupported summary schema in {path}")
    return value


def total_bytes(summary: dict, direction: str) -> int:
    return int(summary["traffic_totals"][direction]["payload_bytes"])


def percent(new: int, old: int) -> float | None:
    return None if old == 0 else 100.0 * (new - old) / old


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", required=True, type=Path)
    parser.add_argument("--right", required=True, type=Path)
    parser.add_argument("--left-label", default="left")
    parser.add_argument("--right-label", default="right")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    left = load(args.left)
    right = load(args.right)
    directions = ["client_to_server", "server_to_client"]
    result = {
        "schema": "rokid.voice-canary.comparison.v1",
        "left_label": args.left_label,
        "right_label": args.right_label,
        "left": {
            "websocket_record_count": left["websocket_record_count"],
            "match_count": left["match_count"],
            "traffic_bytes": {d: total_bytes(left, d) for d in directions},
        },
        "right": {
            "websocket_record_count": right["websocket_record_count"],
            "match_count": right["match_count"],
            "traffic_bytes": {d: total_bytes(right, d) for d in directions},
        },
        "right_vs_left_percent_change": {
            d: percent(total_bytes(right, d), total_bytes(left, d)) for d in directions
        },
        "interpretation": [
            "The comparison describes these captures only.",
            "Traffic totals are not latency or efficiency measurements.",
            "A vendor gateway does not prove the upstream model provider.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Controlled-capture comparison: PASS")
    print(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
