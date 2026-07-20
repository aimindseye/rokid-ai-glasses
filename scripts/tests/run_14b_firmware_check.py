#!/usr/bin/env python3
"""
Rokid Test 14B — firmware update discovery and version-resolution testing.

This runner deliberately separates glasses-disconnected and glasses-connected
testing so the glasses never need to be power-cycled between the two groups.

Run the optional disconnected cold-launch baseline at any convenient time:
  python3 run_14b_firmware_check.py --mode disconnected --zip

Later, after the glasses are already powered on and connected:
  python3 run_14b_firmware_check.py --mode connected --zip --bugreport

Important:
  * The script never restarts or powers off the glasses.
  * It may force-stop/relaunch the Hi Rokid phone app where phase isolation
    requires it.
  * Disconnected mode contains only D1 because the Devices page is disabled.
  * Every phase has its own PCAP and SSL key-log export.
  * MediaStore IDs are baselined before each phase, so older files are not
    downloaded again.
  * Android duplicate names such as `sslkeylogfile.txt (18)` are supported.
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


ROKID_PACKAGE = "com.rokid.sprite.global.aiapp"
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


PHASES: Dict[str, Dict[str, object]] = {
    "D1": {
        "mode": "disconnected",
        "name": "disconnected-cold-launch-idle",
        "title": "Disconnected cold-launch network baseline",
        "restart_app": True,
        "wait_seconds": 60,
        "instructions": (
            "Keep the glasses disconnected. Start a fresh PCAPdroid capture. "
            "The script will relaunch Hi Rokid. Do not attempt to open the "
            "Devices page: it is connection-gated when the glasses are "
            "disconnected. Remain on the normal app screen for 60 seconds."
        ),
        "operator_action": "none",
    },
    "C1": {
        "mode": "connected",
        "name": "connected-cold-launch-idle",
        "title": "Connected cold launch, idle",
        "restart_app": True,
        "wait_seconds": 60,
        "instructions": (
            "The glasses must already be powered on and connected. Do not "
            "restart or power-cycle them. Start a fresh PCAPdroid capture. "
            "The script will relaunch Hi Rokid. Remain on the home screen."
        ),
        "operator_action": "none",
    },
    "C2": {
        "mode": "connected",
        "name": "connected-open-devices-page",
        "title": "Connected, open Devices page without checking",
        "restart_app": False,
        "wait_seconds": 30,
        "instructions": (
            "Keep the same connected glasses and current Hi Rokid session "
            "from C1. Open the Devices page and the connected-glasses detail "
            "view that contains the firmware/update control. Do not press "
            "Check for Updates. This tests whether page entry alone triggers "
            "a version or update request."
        ),
        "operator_action": "open_devices_page",
    },
    "C3": {
        "mode": "connected",
        "name": "connected-manual-check-first",
        "title": "Connected, first explicit Check for Updates",
        "restart_app": False,
        "wait_seconds": 0,
        "instructions": (
            "Keep the same connected glasses and the same Hi Rokid app "
            "session from C2. Start a fresh PCAPdroid capture, then press "
            "Check for Updates exactly once. Do not download firmware if "
            "offered."
        ),
        "operator_action": "manual_check",
    },
    "C4": {
        "mode": "connected",
        "name": "connected-manual-check-repeat",
        "title": "Connected, immediate repeated Check for Updates",
        "restart_app": False,
        "wait_seconds": 0,
        "instructions": (
            "Keep the same connected glasses and same Hi Rokid app session. "
            "Start a fresh capture and press Check for Updates again. This "
            "tests caching, request deduplication, and repeated server calls."
        ),
        "operator_action": "manual_check",
    },
    "C5": {
        "mode": "connected",
        "name": "connected-offline-manual-check",
        "title": "Connected glasses, phone internet offline",
        "restart_app": False,
        "wait_seconds": 0,
        "instructions": (
            "Keep Bluetooth and the glasses connection active, but disable "
            "the phone's internet access. Press Check for Updates once and "
            "record whether the app uses cached data or shows a network "
            "error. Re-enable internet after the phase."
        ),
        "operator_action": "offline_manual_check",
    },
}


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


def prompt_text(message: str, *, allow_empty: bool = True) -> str:
    try:
        value = input(f"\n{message}\n> ").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise TestAbort("Operator aborted the test.") from exc

    if not value and not allow_empty:
        return "not-recorded"
    return value


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


def classify_name(name: str) -> str:
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
        "first_install_time": first(r"\bfirstInstallTime=(.+)"),
        "last_update_time": first(r"\blastUpdateTime=(.+)"),
    }


def write_marker(
    path: Path,
    base: Sequence[str],
    phase_id: str,
    label: str,
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
    kind = classify_name(name)

    if kind in {"pcap", "ssl_keylog"}:
        return True

    logical_name = strip_android_duplicate_suffix(name)
    return kind == "sidecar" and (
        "pcapdroid" in relative_path or "pcapdroid" in logical_name
    )


def new_media_rows(
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
) -> List[Dict[str, object]]:
    selected: List[Dict[str, str]] = []

    for _ in range(6):
        collection_uri, current_rows = query_media_store(base, user_id)
        selected = new_media_rows(
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
        kind = classify_name(original_name)
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
    return pulled


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


def restart_hi_rokid(base: Sequence[str]) -> None:
    adb_shell(
        base,
        "am",
        "force-stop",
        ROKID_PACKAGE,
        check=False,
    )
    time.sleep(1)
    launch_package(base, ROKID_PACKAGE)
    time.sleep(3)


def start_logcat(base: Sequence[str], destination: Path) -> subprocess.Popen:
    destination.parent.mkdir(parents=True, exist_ok=True)
    output = destination.open("wb")
    process = subprocess.Popen(
        [*base, "logcat", "-v", "threadtime"],
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


def capture_screenshot(base: Sequence[str], destination: Path) -> None:
    result = run(
        [*base, "exec-out", "screencap", "-p"],
        check=False,
        text=False,
    )
    if result.returncode == 0 and result.stdout:
        destination.write_bytes(result.stdout)


def capture_ui_xml(base: Sequence[str], destination: Path) -> None:
    remote = "/sdcard/window_dump_14b.xml"
    adb_shell(
        base,
        "uiautomator",
        "dump",
        remote,
        check=False,
    )
    result = run(
        [*base, "exec-out", "cat", remote],
        check=False,
        text=False,
    )
    if result.returncode == 0 and result.stdout:
        destination.write_bytes(result.stdout)
    adb_shell(base, "rm", "-f", remote, check=False)


def write_command_output(
    command: Sequence[str],
    destination: Path,
) -> None:
    result = run(command, check=False)
    destination.write_text(
        result.stdout
        + ("\nSTDERR:\n" + result.stderr if result.stderr else ""),
        encoding="utf-8",
    )


def countdown(seconds: int, label: str) -> None:
    if seconds <= 0:
        return

    print(f"\nObserving {label} for {seconds} seconds.")
    for remaining in range(seconds, 0, -1):
        print(
            f"\rRemaining: {remaining:3d} seconds",
            end="",
            flush=True,
        )
        time.sleep(1)
    print("\rObservation window complete.      ")


def selected_phase_ids(
    mode: str,
    include_offline: bool,
    requested: Optional[str],
) -> List[str]:
    default_ids = (
        ["D1"]
        if mode == "disconnected"
        else ["C1", "C2", "C3", "C4"]
    )
    if mode == "connected" and include_offline:
        default_ids.append("C5")

    if not requested:
        return default_ids

    parsed = [
        item.strip().upper()
        for item in requested.split(",")
        if item.strip()
    ]
    for phase_id in parsed:
        if phase_id not in PHASES:
            raise TestAbort(f"Unknown phase ID: {phase_id}")
        if PHASES[phase_id]["mode"] != mode:
            raise TestAbort(
                f"Phase {phase_id} belongs to mode "
                f"{PHASES[phase_id]['mode']}, not {mode}."
            )
    return parsed


def write_checklist(
    root: Path,
    mode: str,
    phase_ids: Sequence[str],
) -> None:
    lines = [
        "# Test 14B firmware-check operator checklist",
        "",
        f"Mode: **{mode}**",
        "",
        "## Critical hardware rule",
        "",
        "- Do not power-cycle or restart the glasses for this test.",
        "- The runner never sends a glasses restart command.",
        "- App restarts refer only to force-stopping/relaunching Hi Rokid.",
        "",
    ]

    if mode == "disconnected":
        lines += [
            "Keep the glasses disconnected for the entire run.",
            "Disconnected mode intentionally contains only D1.",
            "The Devices page and firmware controls are connection-gated.",
            "Complete this baseline independently of the connected run.",
            "",
        ]
    else:
        lines += [
            "Begin only after the glasses are already powered on and connected.",
            "Keep them connected throughout all connected phases.",
            "C1 relaunches only the Hi Rokid phone app.",
            "C2, C3, and C4 intentionally retain the same app session.",
            "",
        ]

    lines += [
        "## PCAPdroid requirement for every phase",
        "",
        "1. Start a fresh PCAPdroid capture when instructed.",
        "2. Perform only the displayed phase action.",
        "3. Stop capture.",
        "4. Export the raw PCAP/PCAPNG.",
        "5. Export `sslkeylogfile.txt` or equivalent SSL key log.",
        "6. Save exports to a MediaStore-visible folder such as "
        "`Download/PCAPdroid`.",
        "",
        "## Selected phases",
        "",
    ]

    for phase_id in phase_ids:
        phase = PHASES[phase_id]
        lines.append(f"- **{phase_id}** — {phase['title']}")

    (root / "operator-checklist.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run isolated Hi Rokid firmware-update discovery tests while "
            "keeping disconnected and connected glasses testing separate."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("disconnected", "connected"),
        required=True,
        help="Run only the disconnected or connected phase group.",
    )
    parser.add_argument(
        "--serial",
        help="ADB device serial when multiple devices are connected.",
    )
    parser.add_argument(
        "--phases",
        help=(
            "Optional comma-separated phase IDs. Defaults: D1,D2,D3 for "
            "disconnected; C1,C2,C3,C4 for connected."
        ),
    )
    parser.add_argument(
        "--include-offline",
        action="store_true",
        help="Add optional connected offline phase C5.",
    )
    parser.add_argument(
        "--bugreport",
        action="store_true",
        help="Collect an Android bugreport after the selected phases.",
    )
    parser.add_argument(
        "--output",
        help=(
            "Custom output directory. Default is under "
            "~/rokid-nettest/tests/."
        ),
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Create a private evidence ZIP after validation.",
    )
    args = parser.parse_args()

    require_tools(["adb"])
    base = adb_base(args.serial)
    device = validate_device(base)
    user_id = device["current_user"]
    phase_ids = selected_phase_ids(
        args.mode,
        args.include_offline,
        args.phases,
    )

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (
            Path.home()
            / "rokid-nettest"
            / "tests"
            / f"14b-firmware-check-{args.mode}-{timestamp}"
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

    write_checklist(root, args.mode, phase_ids)

    run_info: Dict[str, object] = {
        "schema": "rokid.test-run.v1",
        "test_id": "14b-firmware-update-discovery",
        "mode": args.mode,
        "start_utc": utc_now(),
        "output_directory": str(root),
        "hardware_policy": {
            "glasses_restart_allowed": False,
            "glasses_power_cycle_required": False,
            "hi_rokid_app_restart_allowed": True,
        },
        "known_ui_constraint": {
            "devices_page_requires_connected_glasses": True,
            "firmware_check_unavailable_while_disconnected": True,
            "source": "operator-observed-before-connected-test",
        },
        "device": device,
        "rokid_app": package_version(base, ROKID_PACKAGE),
        "pcapdroid_app": package_version(base, PCAPDROID_PACKAGE),
        "selected_phases": phase_ids,
        "bugreport_requested": args.bugreport,
    }
    (root / "run-info-private.json").write_text(
        json.dumps(run_info, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nRokid Test 14B — Firmware Update Discovery")
    print("===========================================")
    print(f"Mode:          {args.mode}")
    print(f"Output:        {root}")
    print(f"Phone:         {device['manufacturer']} {device['model']}")
    print(f"Android user:  {user_id}")
    print(f"Phases:        {', '.join(phase_ids)}")
    print("Glasses reset: NEVER performed by this script")

    if args.mode == "disconnected":
        prompt_enter(
            "Confirm the glasses are disconnected. You do not need to power "
            "them off if disconnection can be maintained another way."
        )
    else:
        prompt_enter(
            "Confirm the glasses are already powered on, connected, and "
            "stable. Do not restart or power-cycle them during this run."
        )

    # Baseline system evidence.
    system_dir = root / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    write_command_output(
        [*base, "shell", "dumpsys", "bluetooth_manager"],
        system_dir / "bluetooth-manager-before.txt",
    )
    write_command_output(
        [*base, "shell", "dumpsys", "package", ROKID_PACKAGE],
        system_dir / "hi-rokid-package.txt",
    )
    write_command_output(
        [*base, "shell", "dumpsys", "connectivity"],
        system_dir / "connectivity-before.txt",
    )

    phase_results: List[Dict[str, object]] = []

    for sequence, phase_id in enumerate(phase_ids, start=1):
        phase = PHASES[phase_id]
        phase_name = str(phase["name"])
        phase_dir = root / "phases" / f"{sequence:02d}-{phase_id}-{phase_name}"
        phase_dir.mkdir(parents=True, exist_ok=False)

        print("\n" + "=" * 76)
        print(f"{phase_id}: {phase['title']}")
        print("=" * 76)
        print(phase["instructions"])

        prompt_enter(
            "Confirm the phone/glasses state matches this phase and that "
            "PCAPdroid is ready."
        )

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
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        run([*base, "logcat", "-c"], check=False)
        logcat_process = start_logcat(
            base,
            phase_dir / "logcat-private.txt",
        )

        pulled: List[Dict[str, object]] = []
        operator: Dict[str, object] = {}

        try:
            launch_package(base, PCAPDROID_PACKAGE)
            prompt_enter(
                "Start a new PCAPdroid capture for Hi Rokid. Confirm the "
                "capture timer or notification is active."
            )
            write_marker(
                marker_path,
                base,
                phase_id,
                "PCAP_CAPTURE_STARTED",
            )

            if bool(phase["restart_app"]):
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_APP_RESTART_BEGIN",
                )
                restart_hi_rokid(base)
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_APP_RESTART_COMPLETE",
                )
            else:
                launch_package(base, ROKID_PACKAGE)
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_EXISTING_SESSION_REUSED",
                )

            capture_screenshot(base, phase_dir / "before-action.png")
            capture_ui_xml(base, phase_dir / "before-action.xml")

            action = str(phase["operator_action"])

            if action == "none":
                countdown(
                    int(phase["wait_seconds"]),
                    str(phase["title"]),
                )

            elif action == "open_devices_page":
                prompt_enter(
                    "Open Hi Rokid's Devices page, select the connected "
                    "glasses, and open the detail view containing the firmware "
                    "or update control. Do not press Check for Updates. Once "
                    "the page is open, return here."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "DEVICES_FIRMWARE_PAGE_OPENED",
                )
                operator["firmware_version_displayed"] = prompt_text(
                    "Enter the firmware version displayed on the page, or "
                    "leave blank if no version is visible."
                )
                countdown(
                    int(phase["wait_seconds"]),
                    str(phase["title"]),
                )

            elif action in {"manual_check", "offline_manual_check"}:
                if action == "offline_manual_check":
                    prompt_enter(
                        "Disable the phone's internet while keeping Bluetooth "
                        "and the glasses connection active."
                    )
                    write_marker(
                        marker_path,
                        base,
                        phase_id,
                        "PHONE_INTERNET_DISABLED_OPERATOR",
                    )

                prompt_enter(
                    "Remain on or open the Devices page for the connected "
                    "glasses. Record the displayed firmware version, then "
                    "press Check for Updates exactly once. Do not download or "
                    "install firmware if offered."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "CHECK_FOR_UPDATES_PRESSED",
                )

                operator["firmware_version_before_check"] = prompt_text(
                    "Enter the firmware version shown before or during the "
                    "check, or leave blank if none is visible."
                )
                operator["result_text"] = prompt_text(
                    "Enter the exact result shown by Hi Rokid, such as "
                    "'latest version', an available version, a disabled "
                    "button, or a network error."
                )
                operator["update_available"] = ask_yes_no(
                    "Did Hi Rokid report that an update is available?",
                    default=False,
                )
                operator["download_started"] = ask_yes_no(
                    "Was any firmware download started?",
                    default=False,
                )

                if action == "offline_manual_check":
                    prompt_enter(
                        "Re-enable phone internet now, while leaving the "
                        "glasses connected."
                    )
                    write_marker(
                        marker_path,
                        base,
                        phase_id,
                        "PHONE_INTERNET_REENABLED_OPERATOR",
                    )

            capture_screenshot(base, phase_dir / "after-action.png")
            capture_ui_xml(base, phase_dir / "after-action.xml")
            write_marker(
                marker_path,
                base,
                phase_id,
                "PHASE_ACTION_COMPLETE",
                json.dumps(operator, separators=(",", ":")),
            )

            prompt_enter(
                "Stop PCAPdroid and export both the raw PCAP/PCAPNG and the "
                "SSL key log to Download/PCAPdroid. Export any CSV or ZIP "
                "sidecars as well."
            )
            write_marker(
                marker_path,
                base,
                phase_id,
                "PCAP_CAPTURE_STOPPED_AND_EXPORTED",
            )

            pulled = pull_new_exports(
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

        pcap_count = sum(
            item.get("kind") == "pcap"
            for item in pulled
        )
        keylog_count = sum(
            item.get("kind") == "ssl_keylog"
            for item in pulled
        )

        (phase_dir / "pulled-media-private.json").write_text(
            json.dumps(pulled, indent=2) + "\n",
            encoding="utf-8",
        )
        (phase_dir / "operator-observation-private.json").write_text(
            json.dumps(operator, indent=2) + "\n",
            encoding="utf-8",
        )

        write_command_output(
            [*base, "shell", "dumpsys", "bluetooth_manager"],
            phase_dir / "bluetooth-manager-after.txt",
        )
        write_command_output(
            [*base, "shell", "dumpsys", "connectivity"],
            phase_dir / "connectivity-after.txt",
        )

        phase_gate = pcap_count >= 1 and keylog_count >= 1
        phase_result = {
            "sequence": sequence,
            "phase_id": phase_id,
            "phase_name": phase_name,
            "mode": args.mode,
            "restart_hi_rokid_app": bool(phase["restart_app"]),
            "glasses_restart_performed": False,
            "operator": operator,
            "pcap_count": pcap_count,
            "ssl_keylog_count": keylog_count,
            "evidence_gate_pass": phase_gate,
            "phase_directory": str(phase_dir),
            "pulled_media": pulled,
        }
        phase_results.append(phase_result)

        print(
            f"\n{phase_id} evidence: "
            f"{pcap_count} PCAP(s), {keylog_count} SSL key log(s)"
        )
        print(
            f"{phase_id} evidence gate: "
            + ("PASS" if phase_gate else "FAIL")
        )
        write_marker(
            marker_path,
            base,
            phase_id,
            "PHASE_COMPLETE",
            json.dumps(
                {
                    "pcap_count": pcap_count,
                    "ssl_keylog_count": keylog_count,
                    "gate_pass": phase_gate,
                },
                separators=(",", ":"),
            ),
        )

    bugreport_result: Dict[str, object] = {}
    if args.bugreport:
        bugreport_result = collect_bugreport(
            base,
            root / "system" / f"bugreport-14b-{args.mode}.zip",
        )
        (root / "system" / "bugreport-result-private.json").write_text(
            json.dumps(bugreport_result, indent=2) + "\n",
            encoding="utf-8",
        )

    write_command_output(
        [*base, "shell", "dumpsys", "bluetooth_manager"],
        system_dir / "bluetooth-manager-after.txt",
    )
    write_command_output(
        [*base, "shell", "dumpsys", "connectivity"],
        system_dir / "connectivity-after.txt",
    )

    aggregate_pcap_count = sum(
        int(item["pcap_count"]) for item in phase_results
    )
    aggregate_keylog_count = sum(
        int(item["ssl_keylog_count"]) for item in phase_results
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
        "all_phase_gates_pass": all(
            bool(item["evidence_gate_pass"]) for item in phase_results
        ),
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

    print("\nTest 14B evidence summary")
    print("=========================")
    print(f"Mode:                    {args.mode}")
    print(f"Required phases:         {required}")
    print(f"Total PCAP files:        {aggregate_pcap_count}")
    print(f"Total SSL key logs:      {aggregate_keylog_count}")
    print(
        "Aggregate evidence gate: "
        + ("PASS" if aggregate_gate else "FAIL")
    )
    print(f"Evidence directory:      {root}")
    print(f"SHA-256 manifest:        {manifest}")

    if private_zip:
        print(f"Private evidence ZIP:    {private_zip}")
        print(f"ZIP SHA-256:             {sha256_file(private_zip)}")

    if args.mode == "disconnected":
        print(
            "\nDisconnected testing is complete. Run connected mode later, "
            "only after the glasses are already powered on and connected."
        )
    else:
        print(
            "\nConnected testing is complete. No glasses restart was requested "
            "or performed by this script."
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
