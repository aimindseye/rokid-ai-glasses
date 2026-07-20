#!/usr/bin/env python3
"""
Audit and recover complete decryption evidence for Rokid Test 14A-r2.

Recovers:
  * PCAP / PCAPNG / CAP captures
  * PCAPdroid SSL key logs, including sslkeylogfile.txt (18)
  * PCAPdroid CSV/ZIP/JSON/log sidecars in the test time window
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
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

PCAP_SUFFIXES = (".pcap", ".pcapng", ".cap")
SIDECAR_SUFFIXES = (".csv", ".zip", ".json", ".txt", ".log", ".keylog")
SSL_KEYLOG_TOKENS = (
    "sslkeylog",
    "ssl-keylog",
    "ssl_keylog",
    "keylogfile",
    "tlskeylog",
)
MEDIA_PROJECTION = (
    "_id:_display_name:relative_path:date_modified:"
    "date_added:_size:mime_type"
)


class AuditError(RuntimeError):
    pass


def strip_android_duplicate_suffix(name: str) -> str:
    return re.sub(r"\s*\(\d+\)$", "", name.strip().lower())


def has_logical_suffix(name: str, suffixes: Sequence[str]) -> bool:
    return strip_android_duplicate_suffix(name).endswith(tuple(suffixes))


def is_pcap_name(name: str) -> bool:
    return has_logical_suffix(name, PCAP_SUFFIXES)


def is_ssl_keylog_name(name: str) -> bool:
    lowered = strip_android_duplicate_suffix(name)
    return any(token in lowered for token in SSL_KEYLOG_TOKENS)


def classify_name(name: str) -> str:
    if is_pcap_name(name):
        return "pcap"
    if is_ssl_keylog_name(name):
        return "ssl_keylog"
    if has_logical_suffix(name, SIDECAR_SUFFIXES):
        return "sidecar"
    return "other"


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
    result = ["adb"]
    if serial:
        result += ["-s", serial]
    return result


def adb_shell(
    base: Sequence[str],
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess:
    return run([*base, "shell", *args], check=check)


def parse_iso(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def to_int(value: Optional[str]) -> int:
    try:
        return int(value or "0")
    except ValueError:
        return 0


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
    raise AuditError("MediaStore query failed:\n" + "\n".join(failures))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence_files(root: Path, evidence_class: str) -> List[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and classify_name(path.name) == evidence_class
    )


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

    recovery_manifest = root / "evidence-recovery-private.json"
    if recovery_manifest.is_file():
        try:
            data = json.loads(recovery_manifest.read_text(encoding="utf-8"))
            for item in data.get("recovered", []):
                if isinstance(item, dict) and item.get("media_id"):
                    ids.add(str(item["media_id"]))
        except (OSError, json.JSONDecodeError):
            pass
    return ids


def is_relevant_media(row: Dict[str, str]) -> bool:
    name = row.get("_display_name", "")
    path = row.get("relative_path", "").lower()
    kind = classify_name(name)

    if kind in {"pcap", "ssl_keylog"}:
        return True
    return kind == "sidecar" and (
        "pcapdroid" in path
        or "pcapdroid" in strip_android_duplicate_suffix(name)
    )


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
        raise AuditError(f"Could not read {uri}: {error}")
    partial.replace(destination)


def regenerate_sha256sums(root: Path) -> Path:
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
        root.name + "-private-evidence-recovered-r2.zip"
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


def print_inventory(root: Path) -> Tuple[List[Path], List[Path], List[Path]]:
    pcaps = evidence_files(root, "pcap")
    keylogs = evidence_files(root, "ssl_keylog")
    sidecars = evidence_files(root, "sidecar")

    print(f"Actual PCAP files in tree:      {len(pcaps)}")
    print(f"Actual SSL key logs in tree:    {len(keylogs)}")
    print(f"Other sidecars in tree:         {len(sidecars)}")
    print()

    for label, files in (
        ("PCAP", pcaps),
        ("SSLKEYLOG", keylogs),
        ("SIDECAR", sidecars),
    ):
        for path in files:
            print(
                f"{label:<9} {sha256_file(path)}  "
                f"{path.relative_to(root)}  ({path.stat().st_size} bytes)"
            )
    return pcaps, keylogs, sidecars


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--serial")
    parser.add_argument(
        "--recover",
        action="store_true",
        help="Pull unmatched PCAPdroid evidence from the test time window.",
    )
    parser.add_argument(
        "--padding-seconds",
        type=int,
        default=300,
        help="Window padding before/after the run; default: 300.",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Create a new private-evidence ZIP after audit/recovery.",
    )
    args = parser.parse_args()

    root = Path(args.run_dir).expanduser().resolve()
    if not root.is_dir():
        raise AuditError(f"Run directory does not exist: {root}")

    info_path = root / "run-info-private.json"
    if not info_path.is_file():
        raise AuditError(f"Missing {info_path}")

    info = json.loads(info_path.read_text(encoding="utf-8"))
    required = int(
        info.get("required_accepted_slots")
        or info.get("required_accepted_captures")
        or 0
    )

    print("Test 14A-r2 decryption-evidence audit")
    print("======================================")
    print(f"Run directory:                  {root}")
    print(f"Required accepted slots:        {required}")
    pcaps_before, keylogs_before, _ = print_inventory(root)

    gate_before = (
        required > 0
        and len(pcaps_before) >= required
        and len(keylogs_before) >= required
    )
    print()
    print(
        "Decryption-evidence gate before recovery: "
        + ("PASS" if gate_before else "FAIL")
    )

    recovered: List[Dict[str, object]] = []

    if args.recover:
        if shutil.which("adb") is None:
            raise AuditError("adb was not found in PATH")
        base = adb_base(args.serial)
        state = run([*base, "get-state"], check=False)
        if state.returncode != 0 or state.stdout.strip() != "device":
            raise AuditError("No authorized ADB device is connected")

        user_result = adb_shell(
            base,
            "am",
            "get-current-user",
            check=False,
        )
        user_id = user_result.stdout.strip() or "0"

        start_value = str(info.get("start_utc", ""))
        end_value = str(info.get("end_utc", ""))
        if not start_value or not end_value:
            raise AuditError(
                "run-info-private.json lacks start_utc or end_utc"
            )

        start_epoch = (
            int(parse_iso(start_value).timestamp()) - args.padding_seconds
        )
        end_epoch = (
            int(parse_iso(end_value).timestamp()) + args.padding_seconds
        )

        collection_uri, rows = query_media_store(base, user_id)
        already_known_ids = known_media_ids(root)
        candidates: List[Dict[str, str]] = []

        for row in rows:
            media_id = row.get("_id", "")
            if not media_id or media_id in already_known_ids:
                continue
            if not is_relevant_media(row):
                continue

            changed = max(
                to_int(row.get("date_modified")),
                to_int(row.get("date_added")),
            )
            if not (start_epoch <= changed <= end_epoch):
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

        print()
        print(
            "Unmatched MediaStore evidence candidates in run window: "
            f"{len(candidates)}"
        )

        recovery_dir = root / "recovered-media"
        recovery_dir.mkdir(parents=True, exist_ok=True)

        for row in candidates:
            media_id = row["_id"]
            name = row.get("_display_name", f"media-{media_id}")
            kind = classify_name(name)
            safe_name = re.sub(r"[^A-Za-z0-9._() -]+", "_", name)
            destination = (
                recovery_dir
                / f"{kind}--media-{media_id}--{safe_name}"
            )
            uri = f"{collection_uri}/{media_id}"
            content_read_to_file(base, user_id, uri, destination)

            item = {
                "media_id": media_id,
                "kind": kind,
                "uri": uri,
                "original_name": name,
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
                f"Recovered {kind}: {item['destination']} "
                f"({item['actual_size']} bytes)"
            )

        report = {
            "run_directory": str(root),
            "generated_utc": dt.datetime.now(
                dt.timezone.utc
            ).isoformat(),
            "window_start_epoch": start_epoch,
            "window_end_epoch": end_epoch,
            "recovered": recovered,
        }
        (root / "evidence-recovery-private.json").write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

    pcaps_after, keylogs_after, sidecars_after = print_inventory(root)
    gate_after = (
        required > 0
        and len(pcaps_after) >= required
        and len(keylogs_after) >= required
    )

    final_report = {
        "required_accepted_slots": required,
        "pcap_count": len(pcaps_after),
        "ssl_keylog_count": len(keylogs_after),
        "sidecar_count": len(sidecars_after),
        "decryption_evidence_gate_pass": gate_after,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (root / "decryption-evidence-audit-private.json").write_text(
        json.dumps(final_report, indent=2) + "\n",
        encoding="utf-8",
    )
    regenerate_sha256sums(root)

    print()
    print(f"Required accepted slots:        {required}")
    print(f"Final PCAP count:               {len(pcaps_after)}")
    print(f"Final SSL key-log count:        {len(keylogs_after)}")
    print(
        "Final decryption-evidence gate: "
        + ("PASS" if gate_after else "FAIL")
    )

    if args.zip:
        zip_path = make_zip(root)
        print(f"Recovered evidence ZIP:         {zip_path}")
        print(f"ZIP SHA-256:                    {sha256_file(zip_path)}")

    if not gate_after:
        print(
            "ERROR: the run still lacks at least one PCAP and one SSL key "
            "log per required accepted slot.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
