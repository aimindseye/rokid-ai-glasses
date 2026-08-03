#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

WATCH_EVENTS = (
    "connection_attempt_started",
    "callback_cxrl_connected",
    "callback_glass_bt_connected",
    "service_status_result",
    "canonical_image_callback_reregistration_result",
    "photo_ready",
    "operator_gate_prerequisite_ready",
    "qualification_terminal",
)

def now_ms() -> int:
    return time.time_ns() // 1_000_000

def run_capture(argv: list[str], timeout: float = 4.0) -> tuple[int, str]:
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return cp.returncode, (cp.stdout or "") + (cp.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, ""

def adb_shell(adb: str, phone: str, command: str, timeout: float = 4.0) -> tuple[int, str]:
    return run_capture([adb, "-s", phone, "shell", command], timeout=timeout)

def pid_visible(adb: str, phone: str, package: str) -> bool:
    rc, out = adb_shell(adb, phone, f"pidof {package}")
    return rc == 0 and bool(out.strip())

def tail_events(adb: str, phone: str, remote: str) -> list[dict[str, Any]]:
    safe = remote.replace("'", "'\\''")
    rc, out = adb_shell(adb, phone, f"tail -n 120 '{safe}' 2>/dev/null", timeout=5.0)
    if rc != 0:
        return []
    events: list[dict[str, Any]] = []
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events

def snapshot_services(adb: str, phone: str, package: str, path: Path) -> None:
    rc, out = adb_shell(adb, phone, f"dumpsys activity services {package}", timeout=8.0)
    path.write_text(f"COLLECTION_RC={rc}\n{out}", encoding="utf-8")

def append_service_sample(adb: str, phone: str, hi: str, custom: str, path: Path, stamp_ms: int) -> None:
    rc_hi, out_hi = adb_shell(adb, phone, f"dumpsys activity services {hi}", timeout=8.0)
    rc_custom, out_custom = adb_shell(adb, phone, f"dumpsys activity services {custom}", timeout=8.0)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n=== SAMPLE host_epoch_ms={stamp_ms} hi_rc={rc_hi} custom_rc={rc_custom} ===\n")
        f.write("--- HI ROKID ---\n")
        f.write(out_hi)
        if out_hi and not out_hi.endswith("\n"):
            f.write("\n")
        f.write("--- CUSTOM ---\n")
        f.write(out_custom)
        if out_custom and not out_custom.endswith("\n"):
            f.write("\n")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adb", required=True)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--hi-package", required=True)
    ap.add_argument("--custom-package", required=True)
    ap.add_argument("--remote-events", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--duration-seconds", type=float, default=18.0)
    ap.add_argument("--poll-seconds", type=float, default=0.25)
    args = ap.parse_args()

    out = Path(args.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    timeline = out / "timeline-private.jsonl"
    service_samples = out / "service-samples-private.txt"

    start = time.monotonic()
    deadline = start + max(2.0, args.duration_seconds)
    first_seen: dict[str, int] = {}
    prior_hi = pid_visible(args.adb, args.phone, args.hi_package)
    first_sample = True
    first_respawn_ms: int | None = None
    last_service_sample = 0.0

    with timeline.open("w", encoding="utf-8") as tf:
        while time.monotonic() < deadline:
            stamp = now_ms()
            hi = pid_visible(args.adb, args.phone, args.hi_package)
            custom = pid_visible(args.adb, args.phone, args.custom_package)

            sample = {
                "kind": "sample",
                "host_epoch_ms": stamp,
                "hi_process_visible": hi,
                "custom_process_visible": custom,
            }
            tf.write(json.dumps(sample, sort_keys=True) + "\n")
            tf.flush()

            if first_sample:
                tf.write(json.dumps({
                    "kind": "collector_started",
                    "host_epoch_ms": stamp,
                    "hi_process_visible": hi,
                    "custom_process_visible": custom,
                }, sort_keys=True) + "\n")
                tf.flush()
                first_sample = False

            if hi and not prior_hi and first_respawn_ms is None:
                first_respawn_ms = stamp
                tf.write(json.dumps({
                    "kind": "hi_process_first_respawn",
                    "host_epoch_ms": stamp,
                }, sort_keys=True) + "\n")
                tf.flush()
                snapshot_services(
                    args.adb, args.phone, args.hi_package,
                    out / "respawn-hi-services-private.txt"
                )
                snapshot_services(
                    args.adb, args.phone, args.custom_package,
                    out / "respawn-custom-services-private.txt"
                )
                rc_ps, ps_out = adb_shell(args.adb, args.phone, "ps -A", timeout=8.0)
                (out / "respawn-processes-private.txt").write_text(
                    f"COLLECTION_RC={rc_ps}\n{ps_out}", encoding="utf-8"
                )
                rc_proc, proc_out = adb_shell(args.adb, args.phone, "dumpsys activity processes", timeout=12.0)
                (out / "respawn-activity-processes-private.txt").write_text(
                    f"COLLECTION_RC={rc_proc}\n{proc_out}", encoding="utf-8"
                )

            prior_hi = hi

            for event in tail_events(args.adb, args.phone, args.remote_events):
                et = str(event.get("event_type", "")).strip()
                if et in WATCH_EVENTS and et not in first_seen:
                    first_seen[et] = stamp
                    tf.write(json.dumps({
                        "kind": "event_first_seen",
                        "host_epoch_ms": stamp,
                        "event_type": et,
                    }, sort_keys=True) + "\n")
                    tf.flush()

            now_mono = time.monotonic()
            if now_mono - last_service_sample >= 1.0:
                append_service_sample(
                    args.adb, args.phone, args.hi_package, args.custom_package,
                    service_samples, stamp
                )
                last_service_sample = now_mono

            time.sleep(max(0.05, args.poll_seconds))

    summary = {
        "schema": "rokid.test21-r3.collector.v1",
        "collector_duration_seconds": args.duration_seconds,
        "poll_seconds": args.poll_seconds,
        "first_hi_respawn_host_epoch_ms": first_respawn_ms,
        "event_first_seen_host_epoch_ms": first_seen,
    }
    (out / "collector-summary-private.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("TEST21_R3_TIMELINE_COLLECTION=PASS")
    print(f"HI_RESPAWN_OBSERVED={'YES' if first_respawn_ms is not None else 'NO'}")
    for name in WATCH_EVENTS:
        if name in first_seen:
            print(f"EVENT_FIRST_SEEN_{name.upper()}={first_seen[name]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
