#!/usr/bin/env python3
"""Create, append to, and validate a standardized voice-canary timeline."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path
import sys
import time

FIELDS = ["marker", "epoch", "iso_utc", "note"]
ORDER = [
    "BEGIN",
    "VOICE_READY",
    "ACTION_START",
    "ACTION_COMPLETE",
    "RESPONSE_START",
    "RESPONSE_COMPLETE",
    "END",
]


def load(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != FIELDS:
            raise SystemExit(f"ERROR: unexpected timeline columns: {reader.fieldnames}")
        return list(reader)


def write(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def now_row(marker: str, note: str) -> dict[str, str]:
    epoch = time.time()
    iso = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).isoformat()
    return {"marker": marker, "epoch": f"{epoch:.6f}", "iso_utc": iso, "note": note}


def validate(rows: list[dict[str, str]]) -> None:
    markers = [row["marker"] for row in rows]
    duplicates = sorted({marker for marker in markers if markers.count(marker) > 1})
    if duplicates:
        raise SystemExit("ERROR: duplicate markers: " + ", ".join(duplicates))
    observed = [marker for marker in markers if marker in ORDER]
    if observed != ORDER:
        raise SystemExit("ERROR: expected marker order: " + " -> ".join(ORDER))
    epochs = [float(row["epoch"]) for row in rows]
    if epochs != sorted(epochs):
        raise SystemExit("ERROR: timeline epochs are not monotonic")
    print("Timeline validation: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")
    mark = sub.add_parser("mark")
    mark.add_argument("marker", choices=ORDER)
    mark.add_argument("--note", default="")
    sub.add_parser("validate")

    args = parser.parse_args()
    rows = load(args.timeline)

    if args.command == "init":
        if rows:
            raise SystemExit("ERROR: timeline already contains rows")
        write(args.timeline, [])
        print(args.timeline)
        return 0

    if args.command == "mark":
        if any(row["marker"] == args.marker for row in rows):
            raise SystemExit(f"ERROR: marker already exists: {args.marker}")
        expected = ORDER[len(rows)] if len(rows) < len(ORDER) else None
        if args.marker != expected:
            raise SystemExit(f"ERROR: expected next marker {expected}, got {args.marker}")
        rows.append(now_row(args.marker, args.note))
        write(args.timeline, rows)
        print(f"{args.marker}: recorded")
        return 0

    validate(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
