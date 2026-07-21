#!/usr/bin/env python3
"""
Rokid Test 16A — Android background service and network activity discovery.

Purpose
-------
Determine what Rokid-related Android processes continue running and what
network traffic they generate when the Hi Rokid UI is no longer active.

The test distinguishes:

  B1  Hi Rokid removed from Recents only.
  B2  Hi Rokid package force-stopped.
  B3  Hi Rokid force-stopped while the phone screen is off.
  B4  Optional independent Rokid AI service package force-stopped.
  B5  Hi Rokid relaunched as a positive network/process control.

This test does NOT restart or power-cycle the glasses.

Primary questions
-----------------
* Is "Rokid AI Service" part of the Hi Rokid package or a separate package?
* Does it remain alive after the Hi Rokid UI is dismissed?
* Does it remain alive after com.rokid.sprite.global.aiapp is force-stopped?
* Is it restarted by a job, alarm, foreground service, companion association,
  broadcast, Bluetooth event, or another package?
* Which hosts/IPs does it contact in each lifecycle state?
* Are payloads decryptable through PCAPdroid TLS interception?
* Does traffic contain account, device, location, telemetry, AI, update, or
  keepalive data?
* Does screen-off/device-idle state change the behavior?
* If the candidate service package is force-stopped, does it restart?

Important Android distinction
-----------------------------
Removing an app from Recents is not the same as force-stopping its package.
This runner tests both states separately.

Default phases
--------------
B1  UI dismissed only; 10-minute screen-on observation.
B2  Hi Rokid force-stopped; 10-minute screen-on observation.
B3  Hi Rokid force-stopped; 10-minute screen-off observation.
B4  Optional service-package force-stop; 10-minute observation.
B5  Hi Rokid relaunched; 5-minute idle positive control.

Usage
-----
First run without knowing the service package:

  python3 run_16a_rokid_background_service.py \
    --observe-minutes 10 \
    --control-minutes 5 \
    --bugreport \
    --zip

The runner prints and records candidate Rokid packages/processes. If the
independent service package becomes clear, repeat with:

  python3 run_16a_rokid_background_service.py \
    --service-package com.example.rokid.service \
    --observe-minutes 10 \
    --control-minutes 5 \
    --bugreport \
    --zip

Privacy
-------
The output is PRIVATE evidence. It can contain packet captures, TLS secrets,
account/session/device identifiers, precise location, notifications, process
state, Bluetooth data, and decrypted application traffic. Do not commit the
generated run directory or ZIP to a public repository.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


HI_ROKID_PACKAGE = "com.rokid.sprite.global.aiapp"
PCAPDROID_PACKAGE = "com.emanuelef.remote_capture"

MEDIA_PROJECTION = (
    "_id:_display_name:relative_path:date_modified:"
    "date_added:_size:mime_type"
)

PCAP_SUFFIXES = (".pcap", ".pcapng", ".cap")
SIDECAR_SUFFIXES = (
    ".zip",
    ".csv",
    ".txt",
    ".json",
    ".keylog",
    ".log",
)
SSL_KEYLOG_TOKENS = (
    "sslkeylog",
    "ssl-keylog",
    "ssl_keylog",
    "keylogfile",
    "tlskeylog",
)


class TestAbort(RuntimeError):
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


def prompt_enter(message: str) -> None:
    try:
        input(f"\n{message}\nPress Enter to continue... ")
    except (EOFError, KeyboardInterrupt) as exc:
        raise TestAbort("Operator aborted the test.") from exc


def prompt_text(message: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"\n{message}{suffix}\n> ").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise TestAbort("Operator aborted the test.") from exc
    return value or default


def ask_yes_no(message: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        value = input(f"{message} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt) as exc:
        raise TestAbort("Operator aborted the test.") from exc
    if not value:
        return default
    return value in {"y", "yes"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def local_now() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def sanitize_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._() -]+", "_", value.strip())
    return cleaned or "unnamed"


def strip_android_duplicate_suffix(name: str) -> str:
    return re.sub(r"\s*\(\d+\)$", "", name.strip().lower())


def has_logical_suffix(name: str, suffixes: Sequence[str]) -> bool:
    return strip_android_duplicate_suffix(name).endswith(tuple(suffixes))


def is_pcap_name(name: str) -> bool:
    return has_logical_suffix(name, PCAP_SUFFIXES)


def is_ssl_keylog_name(name: str) -> bool:
    lowered = strip_android_duplicate_suffix(name)
    return any(token in lowered for token in SSL_KEYLOG_TOKENS)


def classify_export_name(name: str) -> str:
    if is_pcap_name(name):
        return "pcap"
    if is_ssl_keylog_name(name):
        return "ssl_keylog"
    if has_logical_suffix(name, SIDECAR_SUFFIXES):
        return "sidecar"
    return "other"


def require_tools(names: Iterable[str]) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise TestAbort(
            "Missing required command(s): " + ", ".join(sorted(missing))
        )


def validate_device(base: Sequence[str]) -> Dict[str, str]:
    state = run([*base, "get-state"], check=False)
    if state.returncode != 0 or state.stdout.strip() != "device":
        raise TestAbort(
            "No authorized ADB device is available.\n"
            + state.stderr.strip()
        )

    def prop(name: str) -> str:
        return adb_shell(base, "getprop", name, check=False).stdout.strip()

    serial = run([*base, "get-serialno"], check=False).stdout.strip()
    user_id = adb_shell(
        base,
        "am",
        "get-current-user",
        check=False,
    ).stdout.strip() or "0"

    return {
        "serial": serial,
        "current_user": user_id,
        "manufacturer": prop("ro.product.manufacturer"),
        "model": prop("ro.product.model"),
        "device": prop("ro.product.device"),
        "android_release": prop("ro.build.version.release"),
        "sdk": prop("ro.build.version.sdk"),
        "build_fingerprint": prop("ro.build.fingerprint"),
    }


def package_version(base: Sequence[str], package: str) -> Dict[str, str]:
    result = adb_shell(base, "dumpsys", "package", package, check=False)
    body = result.stdout

    def first(pattern: str) -> str:
        match = re.search(pattern, body)
        return match.group(1).strip() if match else ""

    return {
        "package": package,
        "version_name": first(r"\bversionName=([^\s]+)"),
        "version_code": first(r"\bversionCode=(\d+)"),
        "uid": first(r"\buserId=(\d+)"),
        "first_install_time": first(r"\bfirstInstallTime=(.+)"),
        "last_update_time": first(r"\blastUpdateTime=(.+)"),
    }


def parse_package_list(text: str) -> List[Dict[str, str]]:
    packages: List[Dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        payload = line[len("package:"):]
        package_name, _, uid = payload.partition(" uid:")
        packages.append(
            {
                "package": package_name.strip(),
                "uid": uid.strip(),
            }
        )
    return packages


def discover_candidates(base: Sequence[str]) -> Dict[str, object]:
    package_result = adb_shell(
        base,
        "pm",
        "list",
        "packages",
        "-U",
        check=False,
    )
    packages = parse_package_list(package_result.stdout)

    package_candidates = [
        item
        for item in packages
        if re.search(
            r"(rokid|sprite)",
            item["package"],
            re.IGNORECASE,
        )
    ]

    process_result = adb_shell(
        base,
        "ps",
        "-A",
        "-o",
        "USER,PID,PPID,NAME,ARGS",
        check=False,
    )
    process_lines = [
        line
        for line in process_result.stdout.splitlines()
        if re.search(r"(rokid|sprite)", line, re.IGNORECASE)
    ]

    notification_result = adb_shell(
        base,
        "dumpsys",
        "notification",
        "--noredact",
        check=False,
    )
    notification_lines = [
        line
        for line in notification_result.stdout.splitlines()
        if re.search(r"(rokid|ai service)", line, re.IGNORECASE)
    ]

    service_result = adb_shell(
        base,
        "dumpsys",
        "activity",
        "services",
        check=False,
    )
    service_lines = [
        line
        for line in service_result.stdout.splitlines()
        if re.search(r"(rokid|sprite)", line, re.IGNORECASE)
    ]

    return {
        "captured_utc": utc_now(),
        "package_candidates": package_candidates,
        "process_lines": process_lines,
        "notification_lines": notification_lines,
        "service_lines": service_lines,
        "full_package_list_command_returncode": package_result.returncode,
    }


def write_marker(
    path: Path,
    base: Sequence[str],
    phase_id: str,
    label: str,
    *,
    detail: str = "",
) -> None:
    phone_epoch = adb_shell(
        base,
        "date",
        "+%s",
        check=False,
    ).stdout.strip()
    phone_time = adb_shell(
        base,
        "date",
        "+%Y-%m-%dT%H:%M:%S%z",
        check=False,
    ).stdout.strip()

    fields = [
        utc_now(),
        local_now(),
        phone_epoch,
        phone_time,
        phase_id,
        label,
        detail.replace("\t", " ").replace("\n", " "),
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\t".join(fields) + "\n")


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

    raise TestAbort(
        "MediaStore query failed for external_primary and external:\n"
        + "\n".join(failures)
    )


def media_ids(rows: Iterable[Dict[str, str]]) -> Set[str]:
    return {row["_id"] for row in rows if row.get("_id")}


def to_int(value: Optional[str]) -> int:
    try:
        return int(value or "0")
    except ValueError:
        return 0


def is_relevant_export(row: Dict[str, str]) -> bool:
    name = row.get("_display_name", "")
    relative_path = row.get("relative_path", "").lower()
    kind = classify_export_name(name)

    if kind in {"pcap", "ssl_keylog"}:
        return True

    logical_name = strip_android_duplicate_suffix(name)
    return kind == "sidecar" and (
        "pcapdroid" in relative_path or "pcapdroid" in logical_name
    )


def new_export_rows(
    rows: Iterable[Dict[str, str]],
    baseline_ids: Set[str],
    phase_start_epoch: int,
) -> List[Dict[str, str]]:
    selected: List[Dict[str, str]] = []

    for row in rows:
        media_id = row.get("_id", "")
        if not media_id or media_id in baseline_ids:
            continue
        if not is_relevant_export(row):
            continue

        changed = max(
            to_int(row.get("date_modified")),
            to_int(row.get("date_added")),
        )
        if changed and changed < phase_start_epoch - 120:
            continue

        selected.append(row)

    selected.sort(
        key=lambda row: (
            max(
                to_int(row.get("date_modified")),
                to_int(row.get("date_added")),
            ),
            to_int(row.get("_id")),
        )
    )
    return selected


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
        raise TestAbort(f"MediaStore read failed for {uri}: {error}")

    partial.replace(destination)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pull_new_exports(
    base: Sequence[str],
    user_id: str,
    collection_uri: str,
    baseline_ids: Set[str],
    phase_start_epoch: int,
    destination_dir: Path,
    prefix: str,
) -> Tuple[List[Dict[str, object]], List[Dict[str, str]], str]:
    selected: List[Dict[str, str]] = []
    current_rows: List[Dict[str, str]] = []

    for _ in range(8):
        collection_uri, current_rows = query_media_store(base, user_id)
        selected = new_export_rows(
            current_rows,
            baseline_ids,
            phase_start_epoch,
        )
        if (
            any(is_pcap_name(row.get("_display_name", "")) for row in selected)
            and any(
                is_ssl_keylog_name(row.get("_display_name", ""))
                for row in selected
            )
        ):
            break
        time.sleep(2)

    pulled: List[Dict[str, object]] = []
    for row in selected:
        media_id = row["_id"]
        original_name = row.get("_display_name", f"media-{media_id}")
        kind = classify_export_name(original_name)
        safe_name = sanitize_component(original_name)
        destination = (
            destination_dir
            / f"{prefix}--{kind}--media-{media_id}--{safe_name}"
        )
        uri = f"{collection_uri}/{media_id}"
        content_read_to_file(base, user_id, uri, destination)

        pulled.append(
            {
                "media_id": media_id,
                "kind": kind,
                "uri": uri,
                "original_name": original_name,
                "relative_path": row.get("relative_path", ""),
                "mime_type": row.get("mime_type", ""),
                "reported_size": to_int(row.get("_size")),
                "actual_size": destination.stat().st_size,
                "destination": str(destination),
                "sha256": sha256_file(destination),
            }
        )

    return pulled, current_rows, collection_uri


def launch_package(base: Sequence[str], package: str) -> None:
    adb_shell(
        base,
        "monkey",
        "-p",
        package,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
        check=False,
    )


def start_logcat(base: Sequence[str], destination: Path) -> subprocess.Popen:
    destination.parent.mkdir(parents=True, exist_ok=True)
    output = destination.open("wb")
    process = subprocess.Popen(
        [*base, "logcat", "-b", "all", "-v", "threadtime"],
        stdout=output,
        stderr=subprocess.STDOUT,
    )
    process._output_handle = output  # type: ignore[attr-defined]
    return process


def stop_logcat(process: Optional[subprocess.Popen]) -> None:
    if process is None:
        return

    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    handle = getattr(process, "_output_handle", None)
    if handle:
        handle.close()


def write_command_output(
    command: Sequence[str],
    destination: Path,
) -> None:
    result = run(command, check=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        result.stdout
        + ("\nSTDERR:\n" + result.stderr if result.stderr else ""),
        encoding="utf-8",
    )


def collect_state_bundle(
    base: Sequence[str],
    destination: Path,
    suffix: str,
    candidate_packages: Sequence[str],
) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    commands = {
        f"ps-{suffix}.txt": [
            *base,
            "shell",
            "ps",
            "-A",
            "-o",
            "USER,PID,PPID,NAME,ARGS",
        ],
        f"activity-processes-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "activity",
            "processes",
        ],
        f"activity-services-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "activity",
            "services",
        ],
        f"jobscheduler-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "jobscheduler",
        ],
        f"alarm-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "alarm",
        ],
        f"notification-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "notification",
            "--noredact",
        ],
        f"netstats-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "netstats",
            "detail",
        ],
        f"connectivity-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "connectivity",
        ],
        f"deviceidle-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "deviceidle",
        ],
        f"power-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "power",
        ],
        f"procstats-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "procstats",
            "--hours",
            "3",
        ],
        f"batterystats-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "batterystats",
            "--charged",
        ],
        f"bluetooth-manager-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "bluetooth_manager",
        ],
        f"companiondevice-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "companiondevice",
        ],
        f"ss-{suffix}.txt": [
            *base,
            "shell",
            "sh",
            "-c",
            "ss -tpna 2>&1 || netstat -an 2>&1 || true",
        ],
    }

    for name, command in commands.items():
        write_command_output(command, destination / name)

    for package in candidate_packages:
        safe = sanitize_component(package)
        write_command_output(
            [*base, "shell", "dumpsys", "package", package],
            destination / f"package-{safe}-{suffix}.txt",
        )
        write_command_output(
            [*base, "shell", "cmd", "appops", "get", package],
            destination / f"appops-{safe}-{suffix}.txt",
        )


def periodic_snapshots(
    base: Sequence[str],
    destination: Path,
    duration_seconds: int,
    interval_seconds: int,
    phase_id: str,
    marker_path: Path,
    candidate_packages: Sequence[str],
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    index = 0

    while True:
        elapsed = int(time.monotonic() - start)
        if elapsed > duration_seconds:
            break

        snapshot = destination / f"{index:03d}-{elapsed:05d}s"
        snapshot.mkdir(parents=True, exist_ok=True)

        package_pattern = "|".join(
            [r"rokid", r"sprite"]
            + [re.escape(package) for package in candidate_packages]
        )
        commands = {
            "ps-rokid.txt": [
                *base,
                "shell",
                "sh",
                "-c",
                (
                    "ps -A -o USER,PID,PPID,NAME,ARGS 2>&1 | "
                    f"grep -Ei '{package_pattern}' || true"
                ),
            ],
            "services-rokid.txt": [
                *base,
                "shell",
                "sh",
                "-c",
                (
                    "dumpsys activity services 2>&1 | "
                    f"grep -Ei -B 4 -A 10 '{package_pattern}' || true"
                ),
            ],
            "power.txt": [
                *base,
                "shell",
                "dumpsys",
                "power",
            ],
            "deviceidle.txt": [
                *base,
                "shell",
                "dumpsys",
                "deviceidle",
            ],
            "ss.txt": [
                *base,
                "shell",
                "sh",
                "-c",
                "ss -tpna 2>&1 || netstat -an 2>&1 || true",
            ],
        }
        for name, command in commands.items():
            write_command_output(command, snapshot / name)

        write_marker(
            marker_path,
            base,
            phase_id,
            "PERIODIC_SNAPSHOT",
            detail=f"elapsed_seconds={elapsed}",
        )

        remaining = duration_seconds - int(time.monotonic() - start)
        if remaining <= 0:
            break

        sleep_for = min(interval_seconds, remaining)
        print(
            f"\r{phase_id}: {max(0, remaining):4d}s remaining; "
            f"snapshot {index}",
            end="",
            flush=True,
        )
        time.sleep(sleep_for)
        index += 1

    print(f"\r{phase_id}: observation window complete.          ")


def collect_bugreport(
    base: Sequence[str],
    destination: Path,
) -> Dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print("\nCollecting Android bugreport. This may take several minutes.")
    result = run(
        [*base, "bugreport", str(destination)],
        check=False,
    )

    candidates = sorted(destination.parent.glob(destination.stem + "*.zip"))
    actual = candidates[-1] if candidates else destination

    return {
        "requested_path": str(destination),
        "actual_path": str(actual) if actual.exists() else "",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "sha256": sha256_file(actual) if actual.exists() else "",
        "size": actual.stat().st_size if actual.exists() else 0,
    }


def write_sha256_manifest(root: Path) -> Path:
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


def make_private_zip(root: Path) -> Path:
    destination = root.with_name(root.name + "-private-evidence.zip")
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
    parser = argparse.ArgumentParser(
        description=(
            "Test Rokid-related Android background processes and network "
            "activity while Hi Rokid is dismissed or force-stopped."
        )
    )
    parser.add_argument(
        "--serial",
        help="ADB serial when multiple Android devices are connected.",
    )
    parser.add_argument(
        "--service-package",
        help=(
            "Optional independent Rokid AI service package. Enables B4, "
            "which force-stops that package and observes restart/traffic."
        ),
    )
    parser.add_argument(
        "--observe-minutes",
        type=float,
        default=10.0,
        help="Observation duration for B1-B4. Default: 10 minutes.",
    )
    parser.add_argument(
        "--control-minutes",
        type=float,
        default=5.0,
        help="Observation duration for B5 positive control. Default: 5 minutes.",
    )
    parser.add_argument(
        "--snapshot-seconds",
        type=int,
        default=30,
        help="Periodic process/network snapshot interval. Default: 30 seconds.",
    )
    parser.add_argument(
        "--skip-screen-off",
        action="store_true",
        help="Skip B3 screen-off observation.",
    )
    parser.add_argument(
        "--skip-control",
        action="store_true",
        help="Skip B5 Hi Rokid relaunched positive control.",
    )
    parser.add_argument(
        "--bugreport",
        action="store_true",
        help="Collect one Android bugreport after all phases.",
    )
    parser.add_argument(
        "--output",
        help=(
            "Custom output directory. Default: "
            "~/rokid-nettest/tests/16a-rokid-background-service-<timestamp>"
        ),
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Create a private evidence ZIP after validation.",
    )
    args = parser.parse_args()

    if args.observe_minutes <= 0:
        raise TestAbort("--observe-minutes must be greater than zero.")
    if args.control_minutes <= 0:
        raise TestAbort("--control-minutes must be greater than zero.")
    if args.snapshot_seconds < 10:
        raise TestAbort("--snapshot-seconds must be at least 10.")

    require_tools(["adb"])
    base = adb_base(args.serial)
    device = validate_device(base)
    user_id = device["current_user"]

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (
            Path.home()
            / "rokid-nettest"
            / "tests"
            / f"16a-rokid-background-service-{timestamp}"
        )
    )
    root.mkdir(parents=True, exist_ok=False)

    marker_path = root / "event-markers-private.tsv"
    marker_path.write_text(
        "\t".join(
            [
                "mac_utc",
                "mac_local",
                "phone_epoch",
                "phone_time",
                "phase_id",
                "label",
                "detail",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    discovery = discover_candidates(base)
    candidate_packages = [
        item["package"]
        for item in discovery["package_candidates"]  # type: ignore[index]
    ]
    if HI_ROKID_PACKAGE not in candidate_packages:
        candidate_packages.append(HI_ROKID_PACKAGE)
    if args.service_package and args.service_package not in candidate_packages:
        candidate_packages.append(args.service_package)

    (root / "candidate-discovery-private.json").write_text(
        json.dumps(discovery, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nRokid Test 16A — Background Service and Network Activity")
    print("========================================================")
    print(f"Output:       {root}")
    print(f"Phone:        {device['manufacturer']} {device['model']}")
    print(f"Android:      {device['android_release']}")
    print(f"Hi Rokid:     {HI_ROKID_PACKAGE}")
    print(f"Service pkg:  {args.service_package or 'not supplied'}")
    print(f"Observation:  {args.observe_minutes:g} minutes")
    print(f"Snapshots:    every {args.snapshot_seconds} seconds")
    print("Glasses reset: NEVER performed by this script")
    print("\nCandidate Rokid packages:")
    for package in candidate_packages:
        info = package_version(base, package)
        print(
            f"  - {package}"
            + (f" (uid {info['uid']})" if info["uid"] else "")
        )

    if discovery["process_lines"]:
        print("\nCurrently matching processes:")
        for line in discovery["process_lines"]:  # type: ignore[assignment]
            print(f"  {line}")

    if discovery["notification_lines"]:
        print("\nMatching notification lines:")
        for line in discovery["notification_lines"]:  # type: ignore[assignment]
            print(f"  {line.strip()}")

    prompt_enter(
        "Confirm the glasses are already powered on and stable. Keep their "
        "connection state unchanged for the entire run. Do not restart or "
        "power-cycle them. Ensure PCAPdroid can capture all Rokid-related "
        "packages or all apps, because the independent service package may "
        "not yet be known."
    )

    run_info: Dict[str, object] = {
        "schema": "rokid.test-run.v1",
        "test_id": "16a-rokid-background-service-network",
        "start_utc": utc_now(),
        "device": device,
        "hi_rokid": package_version(base, HI_ROKID_PACKAGE),
        "pcapdroid": package_version(base, PCAPDROID_PACKAGE),
        "service_package": args.service_package or "",
        "candidate_packages": candidate_packages,
        "observe_minutes": args.observe_minutes,
        "control_minutes": args.control_minutes,
        "snapshot_seconds": args.snapshot_seconds,
        "hardware_policy": {
            "glasses_restart_allowed": False,
            "glasses_power_cycle_required": False,
            "glasses_connection_state_should_remain_constant": True,
        },
    }
    (root / "run-info-private.json").write_text(
        json.dumps(run_info, indent=2) + "\n",
        encoding="utf-8",
    )

    system_dir = root / "system"
    collect_state_bundle(
        base,
        system_dir,
        "before-run",
        candidate_packages,
    )

    phases: List[Dict[str, object]] = [
        {
            "id": "B1",
            "name": "ui-dismissed-only",
            "title": "Hi Rokid removed from Recents only",
            "duration": int(args.observe_minutes * 60),
            "action": "dismiss_ui",
        },
        {
            "id": "B2",
            "name": "hi-rokid-force-stopped-screen-on",
            "title": "Hi Rokid force-stopped, screen on",
            "duration": int(args.observe_minutes * 60),
            "action": "force_stop_hi_rokid",
        },
    ]

    if not args.skip_screen_off:
        phases.append(
            {
                "id": "B3",
                "name": "hi-rokid-force-stopped-screen-off",
                "title": "Hi Rokid force-stopped, screen off",
                "duration": int(args.observe_minutes * 60),
                "action": "screen_off",
            }
        )

    if args.service_package:
        phases.append(
            {
                "id": "B4",
                "name": "service-package-force-stopped",
                "title": "Independent Rokid AI service package force-stopped",
                "duration": int(args.observe_minutes * 60),
                "action": "force_stop_service",
            }
        )

    if not args.skip_control:
        phases.append(
            {
                "id": "B5",
                "name": "hi-rokid-open-control",
                "title": "Hi Rokid relaunched, idle positive control",
                "duration": int(args.control_minutes * 60),
                "action": "launch_control",
            }
        )

    phase_results: List[Dict[str, object]] = []

    for sequence, phase in enumerate(phases, start=1):
        phase_id = str(phase["id"])
        phase_name = str(phase["name"])
        phase_dir = root / "phases" / f"{sequence:02d}-{phase_id}-{phase_name}"
        phase_dir.mkdir(parents=True, exist_ok=False)

        print("\n" + "=" * 80)
        print(f"{phase_id}: {phase['title']}")
        print("=" * 80)

        collection_uri, baseline_rows = query_media_store(base, user_id)
        baseline_ids = media_ids(baseline_rows)
        phase_start_epoch = int(time.time())

        (phase_dir / "media-baseline-private.json").write_text(
            json.dumps(
                {
                    "collection_uri": collection_uri,
                    "captured_utc": utc_now(),
                    "media_ids": sorted(
                        baseline_ids,
                        key=lambda value: to_int(value),
                    ),
                    "row_count": len(baseline_rows),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        collect_state_bundle(
            base,
            phase_dir / "state-before",
            "before",
            candidate_packages,
        )

        run([*base, "logcat", "-c"], check=False)
        logcat_process = start_logcat(
            base,
            phase_dir / "logcat-private.txt",
        )

        pulled_exports: List[Dict[str, object]] = []
        operator_notes: Dict[str, object] = {}

        try:
            launch_package(base, PCAPDROID_PACKAGE)
            prompt_enter(
                "Start a fresh PCAPdroid capture. Capture all apps or every "
                "identified Rokid package. Confirm the timer/notification is "
                "active."
            )
            write_marker(
                marker_path,
                base,
                phase_id,
                "PCAP_CAPTURE_STARTED",
            )

            action = str(phase["action"])

            if action == "dismiss_ui":
                prompt_enter(
                    "Open Hi Rokid once if needed, then use Android Recents "
                    "and swipe Hi Rokid away. Do NOT use Force stop. Return "
                    "here without reopening Hi Rokid."
                )
                operator_notes["hi_rokid_removed_from_recents"] = ask_yes_no(
                    "Was Hi Rokid removed from Recents?",
                    default=True,
                )
                operator_notes["rokid_ai_service_still_visible"] = ask_yes_no(
                    "Is the Rokid AI Service still shown as running?",
                    default=True,
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_UI_DISMISSED",
                )

            elif action == "force_stop_hi_rokid":
                adb_shell(
                    base,
                    "am",
                    "force-stop",
                    HI_ROKID_PACKAGE,
                    check=False,
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_FORCE_STOPPED",
                )
                time.sleep(2)
                operator_notes["rokid_ai_service_still_visible"] = ask_yes_no(
                    "After force-stopping Hi Rokid, is Rokid AI Service still "
                    "shown as running?",
                    default=True,
                )

            elif action == "screen_off":
                adb_shell(
                    base,
                    "am",
                    "force-stop",
                    HI_ROKID_PACKAGE,
                    check=False,
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_FORCE_STOPPED",
                )
                prompt_enter(
                    "Turn the PHONE screen off/lock it now. Keep Bluetooth, "
                    "Wi-Fi/mobile data, and the glasses connection unchanged. "
                    "Do not interact with the phone until the timer ends."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "PHONE_SCREEN_OFF_OPERATOR",
                )
                operator_notes["screen_off_observation"] = True

            elif action == "force_stop_service":
                assert args.service_package
                adb_shell(
                    base,
                    "am",
                    "force-stop",
                    args.service_package,
                    check=False,
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "SERVICE_PACKAGE_FORCE_STOPPED",
                    detail=args.service_package,
                )
                time.sleep(2)
                operator_notes["service_package"] = args.service_package

            elif action == "launch_control":
                launch_package(base, HI_ROKID_PACKAGE)
                time.sleep(5)
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_LAUNCHED_CONTROL",
                )
                operator_notes["hi_rokid_opened"] = True

            else:
                raise TestAbort(f"Unsupported action: {action}")

            periodic_snapshots(
                base,
                phase_dir / "snapshots",
                int(phase["duration"]),
                args.snapshot_seconds,
                phase_id,
                marker_path,
                candidate_packages,
            )

            if action == "screen_off":
                prompt_enter(
                    "Unlock the phone now without opening Hi Rokid."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "PHONE_SCREEN_ON_OPERATOR",
                )

            operator_notes["end_service_visible"] = ask_yes_no(
                "At the end of this phase, is Rokid AI Service shown as "
                "running?",
                default=True,
            )
            operator_notes["unexpected_ui_or_notification"] = prompt_text(
                "Record any notification, restart, disconnect, or visible "
                "behavior. Leave blank if none.",
                default="",
            )

            write_marker(
                marker_path,
                base,
                phase_id,
                "PHASE_OBSERVATION_COMPLETE",
                detail=json.dumps(operator_notes, separators=(",", ":")),
            )

            prompt_enter(
                "Stop PCAPdroid and export the raw PCAP/PCAPNG and SSL key "
                "log to Download/PCAPdroid. Export connection CSV/ZIP/JSON "
                "sidecars as well."
            )
            write_marker(
                marker_path,
                base,
                phase_id,
                "PCAP_CAPTURE_STOPPED_AND_EXPORTED",
            )

            (
                pulled_exports,
                _current_rows,
                _collection_uri,
            ) = pull_new_exports(
                base,
                user_id,
                collection_uri,
                baseline_ids,
                phase_start_epoch,
                phase_dir / "pcapdroid-export",
                f"{phase_id}-{phase_name}",
            )
        finally:
            stop_logcat(logcat_process)

        collect_state_bundle(
            base,
            phase_dir / "state-after",
            "after",
            candidate_packages,
        )

        pcap_count = sum(
            item.get("kind") == "pcap"
            for item in pulled_exports
        )
        keylog_count = sum(
            item.get("kind") == "ssl_keylog"
            for item in pulled_exports
        )
        sidecar_count = sum(
            item.get("kind") == "sidecar"
            for item in pulled_exports
        )

        phase_gate = pcap_count >= 1 and keylog_count >= 1

        (phase_dir / "pulled-media-private.json").write_text(
            json.dumps(pulled_exports, indent=2) + "\n",
            encoding="utf-8",
        )
        (phase_dir / "operator-observation-private.json").write_text(
            json.dumps(operator_notes, indent=2) + "\n",
            encoding="utf-8",
        )

        phase_result = {
            "phase_id": phase_id,
            "phase_name": phase_name,
            "title": phase["title"],
            "duration_seconds": phase["duration"],
            "action": phase["action"],
            "pcap_count": pcap_count,
            "ssl_keylog_count": keylog_count,
            "sidecar_count": sidecar_count,
            "evidence_gate_pass": phase_gate,
            "operator": operator_notes,
            "pulled_exports": pulled_exports,
            "glasses_restart_performed": False,
        }
        phase_results.append(phase_result)

        print(
            f"\n{phase_id} evidence: "
            f"{pcap_count} PCAP(s), "
            f"{keylog_count} SSL key log(s), "
            f"{sidecar_count} sidecar(s)"
        )
        print(
            f"{phase_id} evidence gate: "
            + ("PASS" if phase_gate else "FAIL")
        )

    bugreport_result: Dict[str, object] = {}
    if args.bugreport:
        bugreport_result = collect_bugreport(
            base,
            root / "system" / "bugreport-16a-background-service.zip",
        )
        (root / "system" / "bugreport-result-private.json").write_text(
            json.dumps(bugreport_result, indent=2) + "\n",
            encoding="utf-8",
        )

    collect_state_bundle(
        base,
        system_dir,
        "after-run",
        candidate_packages,
    )

    aggregate_pcap_count = sum(
        int(item["pcap_count"]) for item in phase_results
    )
    aggregate_keylog_count = sum(
        int(item["ssl_keylog_count"]) for item in phase_results
    )
    aggregate_sidecar_count = sum(
        int(item["sidecar_count"]) for item in phase_results
    )
    required = len(phase_results)
    aggregate_gate = (
        all(bool(item["evidence_gate_pass"]) for item in phase_results)
        and aggregate_pcap_count >= required
        and aggregate_keylog_count >= required
    )

    run_info["end_utc"] = utc_now()
    run_info["phase_results"] = phase_results
    run_info["bugreport"] = bugreport_result
    run_info["evidence_summary"] = {
        "required_phase_count": required,
        "aggregate_pcap_count": aggregate_pcap_count,
        "aggregate_ssl_keylog_count": aggregate_keylog_count,
        "aggregate_sidecar_count": aggregate_sidecar_count,
        "aggregate_gate_pass": aggregate_gate,
    }
    (root / "run-info-private.json").write_text(
        json.dumps(run_info, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = write_sha256_manifest(root)

    private_zip: Optional[Path] = None
    if args.zip:
        private_zip = make_private_zip(root)

    print("\nTest 16A evidence summary")
    print("=========================")
    print("Scope:                   background process/network discovery")
    print(f"Required phases:         {required}")
    print(f"Total PCAP files:        {aggregate_pcap_count}")
    print(f"Total SSL key logs:      {aggregate_keylog_count}")
    print(f"Total sidecars:          {aggregate_sidecar_count}")
    print(
        "Aggregate evidence gate: "
        + ("PASS" if aggregate_gate else "FAIL")
    )
    print(f"Evidence directory:      {root}")
    print(f"SHA-256 manifest:        {manifest}")

    if private_zip:
        print(f"Private evidence ZIP:    {private_zip}")
        print(f"ZIP SHA-256:             {sha256_file(private_zip)}")

    print(
        "\nTesting is complete. No glasses restart or power-cycle was "
        "requested or performed by this script."
    )

    return 0 if aggregate_gate else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestAbort as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("\nERROR: interrupted by operator.", file=sys.stderr)
        raise SystemExit(130)
