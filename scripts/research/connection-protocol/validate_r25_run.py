#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from r25lib import read_json, verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    required = [
        run / "capture-metadata-private.json",
        run / "timeline-private.ndjson",
        run / "analysis" / "pairing-channel-summary-private.json",
        run / "analysis" / "developer-mode-attribution-private.json",
        run / "analysis" / "r25-summary-private.json",
        run / "publication" / "r25-public-status.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("missing run files: " + ", ".join(missing))
    summary = read_json(run / "analysis" / "r25-summary-private.json")
    if summary.get("schema") != "rokid.r25.capture-summary.v1":
        raise SystemExit("unexpected r25 summary schema")
    public = read_json(run / "publication" / "r25-public-status.json")
    if public["minimal_client"].get("write_events", 0) != 0:
        raise SystemExit("client write event count is nonzero")
    if public["developer_mode"].get("remote_invocation_closed"):
        raise SystemExit("r25 package must not auto-promote remote invocation closure")
    print("R25_STOCK_PAIRING_CHANNEL_CLOSED=NO")
    print("R25_DEVELOPER_MODE_REMOTE_INVOCATION_CLOSED=NO")
    print("R25_MINIMAL_CLIENT_STOCK_SESSION_QUALIFIED=NO")
    print("R1_3_3_2_25_RUN_VALIDATION=PASS_BOUNDED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
