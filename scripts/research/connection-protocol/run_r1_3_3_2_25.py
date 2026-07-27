#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def call(command: list[str], allowed: set[int] | None = None) -> int:
    print("+ " + " ".join(command), flush=True)
    completed = subprocess.run(command)
    if allowed is None:
        allowed = {0}
    if completed.returncode not in allowed:
        raise SystemExit(completed.returncode)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phone-serial")
    parser.add_argument("--glasses-serial")
    parser.add_argument("--phase-set", choices=["pairing", "developer-mode", "both"], default="both")
    parser.add_argument("--collect-bugreport", action="store_true")
    parser.add_argument("--allow-developer-toggle", action="store_true")
    parser.add_argument("--client-log", type=Path)
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    py = sys.executable

    required = [
        "run_r25_stock_capture.py",
        "analyze_r25_capture.py",
        "generate_r25_publication.py",
        "verify_sanitized_r25_publication.py",
        "validate_r25_run.py",
        "finalize_r25.py",
        "r25lib.py",
    ]
    missing = [name for name in required if not (here / name).is_file()]
    if missing:
        for name in missing:
            print(f"R25_REPOSITORY_RUNNER_MISSING={name}", file=sys.stderr)
        print("R25_REPOSITORY_RUNNER_PREFLIGHT=FAIL", file=sys.stderr)
        return 2
    print("R25_REPOSITORY_RUNNER_PREFLIGHT=PASS")

    capture = [py, str(here / "run_r25_stock_capture.py"), "--output", str(args.output), "--phase-set", args.phase_set]
    if args.phone_serial:
        capture += ["--phone-serial", args.phone_serial]
    if args.glasses_serial:
        capture += ["--glasses-serial", args.glasses_serial]
    if args.collect_bugreport:
        capture.append("--collect-bugreport")
    if args.allow_developer_toggle:
        capture.append("--allow-developer-toggle")
    call(capture)

    analysis = [py, str(here / "analyze_r25_capture.py"), "--capture", str(args.output)]
    if args.client_log:
        analysis += ["--client-log", str(args.client_log)]
    call(analysis)
    call([py, str(here / "generate_r25_publication.py"), "--summary", str(args.output / "analysis" / "r25-summary-private.json"), "--output", str(args.output / "publication")])
    call([py, str(here / "verify_sanitized_r25_publication.py"), "--publication", str(args.output / "publication")])
    call([py, str(here / "validate_r25_run.py"), "--run", str(args.output)])
    call([py, str(here / "finalize_r25.py"), "--run", str(args.output)])
    print("R1_3_3_2_25_ACCEPTANCE=PASS_BOUNDED_CAPTURE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
