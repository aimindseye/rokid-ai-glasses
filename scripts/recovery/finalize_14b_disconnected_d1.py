#!/usr/bin/env python3
"""
Finalize an aborted Test 14B disconnected run that completed D1.

This audits the existing D1 evidence tree, updates run-info-private.json,
regenerates SHA256SUMS, and optionally creates a private evidence ZIP.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import List


PCAP_SUFFIXES = (".pcap", ".pcapng", ".cap")
SSL_KEYLOG_TOKENS = (
    "sslkeylog",
    "ssl-keylog",
    "ssl_keylog",
    "keylogfile",
    "tlskeylog",
)


class FinalizeError(RuntimeError):
    pass


def strip_duplicate_suffix(name: str) -> str:
    return re.sub(r"\s*\(\d+\)$", "", name.strip().lower())


def is_pcap(path: Path) -> bool:
    return strip_duplicate_suffix(path.name).endswith(PCAP_SUFFIXES)


def is_keylog(path: Path) -> bool:
    lowered = strip_duplicate_suffix(path.name)
    return any(token in lowered for token in SSL_KEYLOG_TOKENS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(root: Path) -> Path:
    destination = root / "SHA256SUMS-private.txt"
    lines: List[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == destination:
            continue
        if path.name.endswith(".partial"):
            continue
        lines.append(f"{sha256_file(path)}  {path.relative_to(root)}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def make_zip(root: Path) -> Path:
    destination = root.with_name(
        root.name + "-private-evidence-finalized.zip"
    )
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root.parent))
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()

    root = Path(args.run_dir).expanduser().resolve()
    if not root.is_dir():
        raise FinalizeError(f"Run directory does not exist: {root}")

    info_path = root / "run-info-private.json"
    if not info_path.is_file():
        raise FinalizeError(f"Missing {info_path}")

    pcaps = sorted(
        path for path in root.rglob("*")
        if path.is_file() and is_pcap(path)
    )
    keylogs = sorted(
        path for path in root.rglob("*")
        if path.is_file() and is_keylog(path)
    )

    if not pcaps or not keylogs:
        raise FinalizeError(
            "D1 cannot be finalized: at least one PCAP and one SSL key log "
            f"are required. Found {len(pcaps)} PCAP(s), "
            f"{len(keylogs)} key log(s)."
        )

    info = json.loads(info_path.read_text(encoding="utf-8"))
    info["mode"] = "disconnected"
    info["selected_phases"] = ["D1"]
    info["finalization"] = {
        "status": "PASS",
        "classification": "DISCONNECTED_COLD_LAUNCH_BASELINE_ONLY",
        "reason": (
            "Devices page and firmware update controls are disabled while "
            "glasses are disconnected; D2 and D3 are not applicable."
        ),
        "finalized_utc": dt.datetime.now(
            dt.timezone.utc
        ).replace(microsecond=0).isoformat(),
    }
    info["known_ui_constraint"] = {
        "devices_page_requires_connected_glasses": True,
        "firmware_check_unavailable_while_disconnected": True,
        "source": "operator-observed",
    }
    info["evidence_summary"] = {
        "required_phase_count": 1,
        "completed_phase_count": 1,
        "pcap_count": len(pcaps),
        "ssl_keylog_count": len(keylogs),
        "aggregate_gate_pass": True,
        "pcaps": [str(path.relative_to(root)) for path in pcaps],
        "ssl_keylogs": [str(path.relative_to(root)) for path in keylogs],
    }
    info_path.write_text(
        json.dumps(info, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = write_manifest(root)

    print("Test 14B disconnected baseline finalized")
    print("========================================")
    print(f"Run directory:     {root}")
    print(f"PCAP count:        {len(pcaps)}")
    print(f"SSL key-log count: {len(keylogs)}")
    print("Disposition:       PASS — D1 baseline only")
    print(f"Manifest:          {manifest}")

    if args.zip:
        zip_path = make_zip(root)
        print(f"Private ZIP:       {zip_path}")
        print(f"ZIP SHA-256:       {sha256_file(zip_path)}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FinalizeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
