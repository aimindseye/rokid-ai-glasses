#!/usr/bin/env python3
"""
Recover missing MediaStore exports for an aborted Rokid Test 14B D1 run.

The script uses D1's media-baseline-private.json as the boundary. It downloads
only MediaStore records created after that baseline and within a bounded time
window.

Recovered evidence classes:
  * PCAP / PCAPNG / CAP
  * sslkeylogfile.txt variants, including Android names such as
    sslkeylogfile.txt (18)
  * connection.csv / connections.csv
  * other PCAPdroid CSV, ZIP, JSON, TXT, LOG and KEYLOG sidecars

Example:
  python3 recover_14b_d1_media.py \
    --run-dir ~/rokid-nettest/tests/14b-firmware-check-disconnected-20260720-103939 \
    --window-minutes 45
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


MEDIA_PROJECTION = (
    "_id:_display_name:relative_path:date_modified:"
    "date_added:_size:mime_type"
)
PCAP_SUFFIXES = (".pcap", ".pcapng", ".cap")
SIDECAR_SUFFIXES = (
    ".csv",
    ".zip",
    ".json",
    ".txt",
    ".log",
    ".keylog",
)
SSL_KEYLOG_TOKENS = (
    "sslkeylog",
    "ssl-keylog",
    "ssl_keylog",
    "keylogfile",
    "tlskeylog",
)


class RecoveryError(RuntimeError):
    pass


def run(
    cmd: Sequence[str],
    *,
    check: bool = True,
    text: bool = True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        check=check,
        text=text,
        stdout=stdout,
        stderr=stderr,
    )


def adb_base(serial: Optional[str]) -> List[str]:
    command = ["adb"]
    if serial:
        command += ["-s", serial]
    return command


def adb_shell(
    base: Sequence[str],
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess:
    return run([*base, "shell", *args], check=check)


def strip_android_duplicate_suffix(name: str) -> str:
    return re.sub(r"\s*\(\d+\)$", "", name.strip().lower())


def has_logical_suffix(name: str, suffixes: Sequence[str]) -> bool:
    return strip_android_duplicate_suffix(name).endswith(tuple(suffixes))


def is_pcap_name(name: str) -> bool:
    return has_logical_suffix(name, PCAP_SUFFIXES)


def is_ssl_keylog_name(name: str) -> bool:
    lowered = strip_android_duplicate_suffix(name)
    return any(token in lowered for token in SSL_KEYLOG_TOKENS)


def is_connection_csv_name(name: str) -> bool:
    lowered = strip_android_duplicate_suffix(name)
    return (
        lowered.endswith(".csv")
        and (
            "connection" in lowered
            or "connections" in lowered
        )
    )


def classify_name(name: str) -> str:
    if is_pcap_name(name):
        return "pcap"
    if is_ssl_keylog_name(name):
        return "ssl_keylog"
    if is_connection_csv_name(name):
        return "connection_csv"
    if has_logical_suffix(name, SIDECAR_SUFFIXES):
        return "sidecar"
    return "other"


def sanitize_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._() -]+", "_", value.strip())
    return cleaned or "unnamed"


def to_int(value: Optional[str]) -> int:
    try:
        return int(value or "0")
    except ValueError:
        return 0


def parse_iso(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def parse_content_rows(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("Row:"):
            continue

        payload = re.sub(r"^Row:\s*\d+\s*", "", line, count=1)
        parts = re.split(
            r",\s+(?=[A-Za-z_][A-Za-z0-9_]*=)",
            payload,
        )
        row: Dict[str, str] = {}

        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            row[key.strip()] = value.strip()

        if row.get("_id"):
            rows.append(row)

    return rows


def query_media_store(
    base: Sequence[str],
    user_id: str,
) -> Tuple[str, List[Dict[str, str]]]:
    failures: List[str] = []

    for volume in ("external_primary", "external"):
        uri = f"content://media/{volume}/file"
        result = adb_shell(
            base,
            "content",
            "query",
            "--user",
            user_id,
            "--uri",
            uri,
            "--projection",
            MEDIA_PROJECTION,
            check=False,
        )
        combined = (result.stdout + "\n" + result.stderr).strip()

        if result.returncode == 0 and "Exception" not in combined:
            return uri, parse_content_rows(result.stdout)

        failures.append(f"{volume}: {combined}")

    raise RecoveryError(
        "MediaStore query failed for external_primary and external:\n"
        + "\n".join(failures)
    )


def locate_d1_phase_dir(root: Path) -> Path:
    matches = sorted(root.glob("phases/*-D1-*"))
    if not matches:
        raise RecoveryError(
            "Could not find a D1 phase directory under "
            f"{root / 'phases'}"
        )
    if len(matches) > 1:
        raise RecoveryError(
            "Multiple D1 phase directories were found:\n"
            + "\n".join(str(path) for path in matches)
        )
    return matches[0]


def read_baseline(d1_dir: Path) -> Tuple[Set[str], int, Path]:
    baseline_path = d1_dir / "media-baseline-private.json"
    if not baseline_path.is_file():
        raise RecoveryError(f"Missing D1 baseline: {baseline_path}")

    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    ids = {str(value) for value in data.get("media_ids", [])}

    captured_utc = str(data.get("captured_utc", ""))
    if not captured_utc:
        raise RecoveryError(
            f"{baseline_path} does not contain captured_utc"
        )

    start_epoch = int(parse_iso(captured_utc).timestamp())
    return ids, start_epoch, baseline_path


def known_media_ids(root: Path) -> Set[str]:
    ids: Set[str] = set()

    for manifest in root.rglob("pulled-media-private.json"):
        try:
            items = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(items, list):
            continue

        for item in items:
            if isinstance(item, dict) and item.get("media_id"):
                ids.add(str(item["media_id"]))

    recovery_path = root / "d1-media-recovery-private.json"
    if recovery_path.is_file():
        try:
            data = json.loads(recovery_path.read_text(encoding="utf-8"))
            for item in data.get("recovered", []):
                if isinstance(item, dict) and item.get("media_id"):
                    ids.add(str(item["media_id"]))
        except (OSError, json.JSONDecodeError):
            pass

    return ids


def is_relevant_media(row: Dict[str, str]) -> bool:
    name = row.get("_display_name", "")
    relative_path = row.get("relative_path", "").lower()
    logical_name = strip_android_duplicate_suffix(name)
    kind = classify_name(name)

    if kind in {"pcap", "ssl_keylog", "connection_csv"}:
        return True

    return kind == "sidecar" and (
        "pcapdroid" in relative_path
        or "pcapdroid" in logical_name
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_read_to_file(
    base: Sequence[str],
    user_id: str,
    uri: str,
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")

    with partial.open("wb") as output:
        process = subprocess.run(
            [
                *base,
                "exec-out",
                "content",
                "read",
                "--user",
                user_id,
                "--uri",
                uri,
            ],
            stdout=output,
            stderr=subprocess.PIPE,
            check=False,
        )

    if process.returncode != 0:
        partial.unlink(missing_ok=True)
        error = process.stderr.decode("utf-8", errors="replace").strip()
        raise RecoveryError(
            f"MediaStore read failed for {uri}: "
            + (error or f"exit {process.returncode}")
        )

    partial.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recover missing D1 PCAPdroid exports using the phase's "
            "MediaStore baseline."
        )
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--serial")
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=45,
        help=(
            "Maximum time after the D1 baseline to consider; default: 45."
        ),
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List matching MediaStore candidates without downloading.",
    )
    args = parser.parse_args()

    if args.window_minutes <= 0:
        parser.error("--window-minutes must be greater than zero")

    if shutil.which("adb") is None:
        raise RecoveryError("adb was not found in PATH")

    root = Path(args.run_dir).expanduser().resolve()
    if not root.is_dir():
        raise RecoveryError(f"Run directory does not exist: {root}")

    d1_dir = locate_d1_phase_dir(root)
    baseline_ids, start_epoch, baseline_path = read_baseline(d1_dir)
    end_epoch = start_epoch + (args.window_minutes * 60)

    base = adb_base(args.serial)
    state = run([*base, "get-state"], check=False)
    if state.returncode != 0 or state.stdout.strip() != "device":
        raise RecoveryError("No authorized ADB device is connected")

    user_id = adb_shell(
        base,
        "am",
        "get-current-user",
        check=False,
    ).stdout.strip() or "0"

    collection_uri, rows = query_media_store(base, user_id)
    already_known = known_media_ids(root)

    candidates: List[Dict[str, str]] = []
    for row in rows:
        media_id = row.get("_id", "")
        if not media_id:
            continue
        if media_id in baseline_ids:
            continue
        if media_id in already_known:
            continue
        if not is_relevant_media(row):
            continue

        changed = max(
            to_int(row.get("date_modified")),
            to_int(row.get("date_added")),
        )
        if not (start_epoch - 120 <= changed <= end_epoch):
            continue

        candidates.append(row)

    candidates.sort(
        key=lambda row: (
            max(
                to_int(row.get("date_modified")),
                to_int(row.get("date_added")),
            ),
            to_int(row.get("_id")),
        )
    )

    print("Test 14B D1 MediaStore recovery")
    print("================================")
    print(f"Run directory:       {root}")
    print(f"D1 phase directory:  {d1_dir}")
    print(f"Baseline file:       {baseline_path}")
    print(
        "Recovery window:     "
        + dt.datetime.fromtimestamp(
            start_epoch,
            tz=dt.timezone.utc,
        ).isoformat()
        + " through "
        + dt.datetime.fromtimestamp(
            end_epoch,
            tz=dt.timezone.utc,
        ).isoformat()
    )
    print(f"Candidates found:    {len(candidates)}")
    print()

    for row in candidates:
        changed = max(
            to_int(row.get("date_modified")),
            to_int(row.get("date_added")),
        )
        print(
            f"[{classify_name(row.get('_display_name', ''))}] "
            f"media={row.get('_id')} "
            f"{row.get('relative_path', '')}"
            f"{row.get('_display_name', '')} "
            f"size={row.get('_size', '0')} "
            f"changed={changed}"
        )

    if args.list_only:
        return 0

    recovery_dir = d1_dir / "recovered-media"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    recovered: List[Dict[str, object]] = []

    for row in candidates:
        media_id = row["_id"]
        original_name = row.get("_display_name", f"media-{media_id}")
        kind = classify_name(original_name)
        safe_name = sanitize_component(original_name)
        destination = (
            recovery_dir
            / f"{kind}--media-{media_id}--{safe_name}"
        )
        uri = f"{collection_uri}/{media_id}"

        content_read_to_file(
            base,
            user_id,
            uri,
            destination,
        )

        item = {
            "media_id": media_id,
            "kind": kind,
            "uri": uri,
            "original_name": original_name,
            "relative_path": row.get("relative_path", ""),
            "date_modified": to_int(row.get("date_modified")),
            "date_added": to_int(row.get("date_added")),
            "reported_size": to_int(row.get("_size")),
            "actual_size": destination.stat().st_size,
            "destination": str(destination.relative_to(root)),
            "sha256": sha256_file(destination),
        }
        recovered.append(item)
        print(
            f"Recovered {kind}: "
            f"{item['destination']} "
            f"({item['actual_size']} bytes)"
        )

    report = {
        "run_directory": str(root),
        "d1_phase_directory": str(d1_dir),
        "baseline_file": str(baseline_path),
        "collection_uri": collection_uri,
        "window_start_epoch": start_epoch,
        "window_end_epoch": end_epoch,
        "generated_utc": dt.datetime.now(
            dt.timezone.utc
        ).replace(microsecond=0).isoformat(),
        "recovered": recovered,
    }
    report_path = root / "d1-media-recovery-private.json"
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    pcap_count = sum(item["kind"] == "pcap" for item in recovered)
    keylog_count = sum(
        item["kind"] == "ssl_keylog"
        for item in recovered
    )
    connection_count = sum(
        item["kind"] == "connection_csv"
        for item in recovered
    )

    print()
    print("Recovery summary")
    print("----------------")
    print(f"Recovered PCAPs:          {pcap_count}")
    print(f"Recovered SSL key logs:   {keylog_count}")
    print(f"Recovered connection CSV: {connection_count}")
    print(f"Recovery report:          {report_path}")
    print()
    print(
        "Now rerun finalize_14b_disconnected_d1.py against the same "
        "--run-dir."
    )

    # A missing PCAP is fatal. An existing key log may already be in the tree,
    # so the finalizer performs the authoritative combined evidence check.
    return 0 if pcap_count >= 1 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RecoveryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("ERROR: interrupted by operator.", file=sys.stderr)
        raise SystemExit(130)
