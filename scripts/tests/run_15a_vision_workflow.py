#!/usr/bin/env python3
"""
Rokid Test 15A — visual-model workflow discovery.

Purpose
-------
Map the end-to-end visual request workflow of the display-free Rokid AI
Glasses Style and Hi Rokid. This is NOT an accuracy benchmark.

The test records:
  * when visual capture is triggered;
  * whether opening a visual feature creates network/device activity;
  * how ChatGPT and Gemini selections affect model/session parameters;
  * whether the same visual-language model identifier is used;
  * whether repeated requests create fresh image/media activity;
  * whether a follow-up reuses visual context;
  * optional offline behavior;
  * PCAP, TLS key log, PCAPdroid sidecars, logcat, UI, system state, and
    MediaStore deltas.

Visual target
-------------
Use an iPad mini displaying locally stored, non-sensitive photos full-screen.

Default target mapping:
  PHOTO-A: V0, V1, V2, V3
  PHOTO-B: V4, V5
  PHOTO-C: optional V6

V2 and V3 MUST use the exact same iPad photo without changing position,
brightness, zoom, orientation, glasses position, or lighting.

Hardware policy
---------------
  * The script never restarts or powers off the glasses.
  * The glasses must already be powered on, connected, and stable.
  * Hi Rokid may be force-stopped/relaunched where session isolation requires.
  * V4 and V5 intentionally preserve the Gemini app session from V3/V4.
  * Every phase has its own PCAP and SSL key-log export.

Default phases
--------------
  V0  Connected cold-launch idle baseline, ChatGPT, PHOTO-A
  V1  Open visual entry only; no visual request, ChatGPT, PHOTO-A
  V2  Fresh ChatGPT visual request, PHOTO-A
  V3  Fresh Gemini visual request, exact same PHOTO-A
  V4  Same Gemini session, fresh visual request after changing to PHOTO-B
  V5  Same Gemini session, context follow-up while PHOTO-B remains displayed
  V6  Optional phone-internet-offline visual request, PHOTO-C

Examples
--------
  python3 run_15a_vision_workflow.py --zip --bugreport

  python3 run_15a_vision_workflow.py \
    --photo-a "A-landscape" \
    --photo-b "B-household-objects" \
    --photo-c "C-sign" \
    --zip

  python3 run_15a_vision_workflow.py \
    --phases V0,V2,V3,V4,V5 \
    --zip

  python3 run_15a_vision_workflow.py \
    --include-offline \
    --pull-new-phone-images \
    --zip

Privacy
-------
The output is private evidence. It may contain packet captures, TLS secrets,
screenshots, logs, media metadata, device identifiers, account/session data,
and images captured by the phone/app. Do not commit the generated run directory
or ZIP to a public repository.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import mimetypes
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
IMAGE_SUFFIXES = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".heic",
    ".heif",
    ".avif",
    ".gif",
    ".bmp",
    ".dng",
)
VIDEO_SUFFIXES = (
    ".mp4",
    ".mov",
    ".m4v",
    ".3gp",
    ".webm",
    ".mkv",
)
AUDIO_SUFFIXES = (
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".flac",
)


DEFAULT_VISION_QUESTION = "What do you see in front of me?"
DEFAULT_FOLLOWUP_QUESTION = (
    "Tell me one more thing about the image you just saw."
)


PHASES: Dict[str, Dict[str, object]] = {
    "V0": {
        "name": "connected-cold-launch-idle",
        "title": "Connected cold-launch idle baseline",
        "model": "ChatGPT",
        "photo_key": "A",
        "restart_app": True,
        "preserve_session_from": "",
        "action": "idle",
        "wait_seconds": 60,
        "instructions": (
            "Display PHOTO-A full-screen on the iPad. Confirm ChatGPT is "
            "selected in Hi Rokid. Start a fresh PCAPdroid capture. The "
            "script will relaunch only Hi Rokid. Do not invoke the assistant "
            "or camera. Remain idle for 60 seconds."
        ),
    },
    "V1": {
        "name": "open-visual-entry-no-request",
        "title": "Open visual feature/entry without making a request",
        "model": "ChatGPT",
        "photo_key": "A",
        "restart_app": False,
        "preserve_session_from": "V0",
        "action": "open_feature",
        "wait_seconds": 30,
        "instructions": (
            "Keep PHOTO-A, the glasses position, and the current ChatGPT app "
            "session unchanged. If Hi Rokid has a visual-assistant, camera, "
            "or image-analysis entry point, open it without invoking a "
            "request. If no separate entry exists, record that fact and "
            "remain on the normal assistant screen."
        ),
    },
    "V2": {
        "name": "chatgpt-vision-photo-a",
        "title": "Fresh ChatGPT visual request using PHOTO-A",
        "model": "ChatGPT",
        "photo_key": "A",
        "restart_app": True,
        "preserve_session_from": "",
        "action": "vision_request",
        "wait_seconds": 0,
        "instructions": (
            "Keep the exact PHOTO-A displayed full-screen. Confirm ChatGPT "
            "is selected. The script will relaunch only Hi Rokid to create a "
            "fresh app/session boundary. Use the fixed visual question."
        ),
    },
    "V3": {
        "name": "gemini-vision-photo-a",
        "title": "Fresh Gemini visual request using the same PHOTO-A",
        "model": "Gemini",
        "photo_key": "A",
        "restart_app": True,
        "preserve_session_from": "",
        "action": "vision_request",
        "wait_seconds": 0,
        "instructions": (
            "Do not change the iPad photo, zoom, orientation, brightness, "
            "distance, lighting, or glasses position from V2. Select Gemini. "
            "The script will relaunch only Hi Rokid. Use the identical fixed "
            "visual question."
        ),
    },
    "V4": {
        "name": "gemini-fresh-vision-photo-b",
        "title": "Same Gemini session, fresh visual request after PHOTO-B",
        "model": "Gemini",
        "photo_key": "B",
        "restart_app": False,
        "preserve_session_from": "V3",
        "action": "vision_request",
        "wait_seconds": 0,
        "instructions": (
            "Keep Gemini selected and preserve the current app session from "
            "V3. Change the iPad to PHOTO-B, wait for the screen to settle, "
            "and use the same visual question. This tests fresh capture, "
            "new image/media activity, and cache behavior."
        ),
    },
    "V5": {
        "name": "gemini-context-followup-photo-b",
        "title": "Same Gemini session, context follow-up with PHOTO-B",
        "model": "Gemini",
        "photo_key": "B",
        "restart_app": False,
        "preserve_session_from": "V4",
        "action": "context_followup",
        "wait_seconds": 0,
        "instructions": (
            "Keep Gemini, PHOTO-B, and the current app session unchanged. "
            "Do not deliberately open a separate camera or visual entry. Ask "
            "the fixed follow-up question. The answer is not scored; this "
            "phase tests whether a new image is captured or prior visual "
            "context is reused."
        ),
    },
    "V6": {
        "name": "gemini-offline-vision-photo-c",
        "title": "Optional offline visual request using PHOTO-C",
        "model": "Gemini",
        "photo_key": "C",
        "restart_app": False,
        "preserve_session_from": "V5",
        "action": "offline_vision_request",
        "wait_seconds": 0,
        "instructions": (
            "Keep the glasses connected over Bluetooth and retain the "
            "current Gemini app session. Display PHOTO-C. Disable the "
            "phone's internet access without disabling Bluetooth, then make "
            "the fixed visual request. Re-enable internet after recording "
            "the result."
        ),
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


def ask_choice(
    message: str,
    choices: Sequence[str],
    *,
    default: str,
) -> str:
    normalized = {choice.lower(): choice for choice in choices}
    rendered = "/".join(choices)
    while True:
        value = prompt_text(
            f"{message} ({rendered})",
            default=default,
        )
        selected = normalized.get(value.lower())
        if selected:
            return selected
        print(f"Choose one of: {rendered}")


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


def classify_media_row(row: Dict[str, str]) -> str:
    name = strip_android_duplicate_suffix(row.get("_display_name", ""))
    mime = row.get("mime_type", "").lower()

    if mime.startswith("image/") or name.endswith(IMAGE_SUFFIXES):
        return "image"
    if mime.startswith("video/") or name.endswith(VIDEO_SUFFIXES):
        return "video"
    if mime.startswith("audio/") or name.endswith(AUDIO_SUFFIXES):
        return "audio"
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
    *,
    model: str = "",
    photo_id: str = "",
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
        model,
        photo_id,
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


def new_phone_media_rows(
    rows: Iterable[Dict[str, str]],
    baseline_ids: Set[str],
    phase_start_epoch: int,
) -> List[Dict[str, str]]:
    selected: List[Dict[str, str]] = []

    for row in rows:
        media_id = row.get("_id", "")
        if not media_id or media_id in baseline_ids:
            continue

        changed = max(
            to_int(row.get("date_modified")),
            to_int(row.get("date_added")),
        )
        if changed and changed < phase_start_epoch - 120:
            continue

        kind = classify_media_row(row)
        if kind not in {"image", "video", "audio"}:
            continue

        relative_path = row.get("relative_path", "").lower()
        name = row.get("_display_name", "")
        if (
            "pcapdroid" in relative_path
            or is_pcap_name(name)
            or is_ssl_keylog_name(name)
        ):
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


def pull_phone_media_candidates(
    base: Sequence[str],
    user_id: str,
    collection_uri: str,
    rows: Sequence[Dict[str, str]],
    destination_dir: Path,
    prefix: str,
) -> List[Dict[str, object]]:
    pulled: List[Dict[str, object]] = []

    for row in rows:
        media_id = row["_id"]
        original_name = row.get("_display_name", f"media-{media_id}")
        kind = classify_media_row(row)
        safe_name = sanitize_component(original_name)
        extension = Path(strip_android_duplicate_suffix(original_name)).suffix
        if not extension:
            extension = mimetypes.guess_extension(
                row.get("mime_type", "")
            ) or ""
        if Path(strip_android_duplicate_suffix(original_name)).suffix:
            destination_name = (
                f"{prefix}--{kind}--media-{media_id}--{safe_name}"
            )
        else:
            destination_name = (
                f"{prefix}--{kind}--media-{media_id}--"
                f"{safe_name}{extension}"
            )
        destination = destination_dir / destination_name
        uri = f"{collection_uri}/{media_id}"
        try:
            content_read_to_file(base, user_id, uri, destination)
        except TestAbort as exc:
            pulled.append(
                {
                    "media_id": media_id,
                    "kind": kind,
                    "uri": uri,
                    "original_name": original_name,
                    "error": str(exc),
                }
            )
            continue

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
    time.sleep(4)


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


def capture_screenshot(base: Sequence[str], destination: Path) -> None:
    result = run(
        [*base, "exec-out", "screencap", "-p"],
        check=False,
        text=False,
    )
    if result.returncode == 0 and result.stdout:
        destination.write_bytes(result.stdout)


def capture_ui_xml(base: Sequence[str], destination: Path) -> None:
    remote = "/sdcard/window_dump_15a.xml"
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
    destination.parent.mkdir(parents=True, exist_ok=True)
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
    include_offline: bool,
    requested: Optional[str],
) -> List[str]:
    default_ids = ["V0", "V1", "V2", "V3", "V4", "V5"]
    if include_offline:
        default_ids.append("V6")

    if not requested:
        return default_ids

    parsed = [
        item.strip().upper()
        for item in requested.split(",")
        if item.strip()
    ]
    if not parsed:
        raise TestAbort("--phases did not contain any phase IDs.")

    for phase_id in parsed:
        if phase_id not in PHASES:
            raise TestAbort(f"Unknown phase ID: {phase_id}")

    if "V6" in parsed and not include_offline:
        print(
            "NOTE: V6 was explicitly requested, so offline testing is enabled."
        )

    # Preserve caller order but reject duplicates.
    seen: Set[str] = set()
    unique: List[str] = []
    for phase_id in parsed:
        if phase_id in seen:
            raise TestAbort(f"Duplicate phase ID: {phase_id}")
        seen.add(phase_id)
        unique.append(phase_id)
    return unique


def validate_phase_dependencies(phase_ids: Sequence[str]) -> None:
    selected = set(phase_ids)

    if "V5" in selected and "V4" not in selected:
        print(
            "WARNING: V5 is designed to follow V4 in the same app session. "
            "The runner will continue, but context-reuse interpretation may "
            "be limited."
        )
    if "V4" in selected and "V3" not in selected:
        print(
            "WARNING: V4 is designed to preserve the Gemini session from V3."
        )
    if "V1" in selected and "V0" not in selected:
        print(
            "WARNING: V1 is designed to preserve the ChatGPT session from V0."
        )


def photo_id_for_phase(
    phase: Dict[str, object],
    photos: Dict[str, str],
) -> str:
    key = str(phase["photo_key"])
    return photos[key]


def write_checklist(
    root: Path,
    phase_ids: Sequence[str],
    photos: Dict[str, str],
    vision_question: str,
    followup_question: str,
    pull_new_images: bool,
) -> None:
    lines = [
        "# Test 15A visual workflow operator checklist",
        "",
        "## Scope",
        "",
        "This test discovers the visual request workflow. It does not score "
        "answer accuracy or rank ChatGPT versus Gemini.",
        "",
        "## Critical hardware rules",
        "",
        "- Begin only after the glasses are powered on, connected, and stable.",
        "- Do not restart or power-cycle the glasses during this run.",
        "- App restarts refer only to Hi Rokid on the phone.",
        "- V4 and V5 intentionally preserve the Gemini app session.",
        "",
        "## iPad preparation",
        "",
        "- Use locally stored, non-sensitive images.",
        "- Put the iPad in airplane mode or Focus mode.",
        "- Disable notifications and auto-lock.",
        "- Disable True Tone/Night Shift and auto-brightness if practical.",
        "- Use fixed brightness, orientation, zoom, distance, and lighting.",
        "- V2 and V3 must use the exact same PHOTO-A without movement.",
        "",
        "## Photo IDs",
        "",
        f"- PHOTO-A: `{photos['A']}`",
        f"- PHOTO-B: `{photos['B']}`",
        f"- PHOTO-C: `{photos['C']}`",
        "",
        "## Fixed questions",
        "",
        f"- Visual request: `{vision_question}`",
        f"- Context follow-up: `{followup_question}`",
        "",
        "## PCAPdroid requirement for every phase",
        "",
        "1. Start a fresh PCAPdroid capture when instructed.",
        "2. Perform only the displayed action.",
        "3. Stop the capture.",
        "4. Export the raw PCAP/PCAPNG.",
        "5. Export the SSL key log.",
        "6. Export any connection CSV/ZIP/JSON sidecars.",
        "7. Save exports to a MediaStore-visible folder.",
        "",
        "## Phone media handling",
        "",
        (
            "- Newly created image/video/audio MediaStore rows are recorded."
        ),
        (
            "- Candidate phone images are pulled into private evidence."
            if pull_new_images
            else "- Candidate phone images are not pulled unless "
            "`--pull-new-phone-images` is used."
        ),
        "",
        "## Selected phases",
        "",
    ]

    for phase_id in phase_ids:
        phase = PHASES[phase_id]
        lines.append(
            f"- **{phase_id}** — {phase['title']} — "
            f"{phase['model']} — PHOTO-{phase['photo_key']}"
        )

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


def collect_phase_system_state(
    base: Sequence[str],
    destination: Path,
    suffix: str,
) -> None:
    commands = {
        f"bluetooth-manager-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "bluetooth_manager",
        ],
        f"connectivity-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "connectivity",
        ],
        f"media-camera-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "media.camera",
        ],
        f"activity-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "activity",
            "activities",
        ],
        f"window-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "window",
            "windows",
        ],
    }
    for name, command in commands.items():
        write_command_output(command, destination / name)


def record_response_observation(
    operator: Dict[str, object],
    *,
    action: str,
) -> None:
    operator["response_completed"] = ask_yes_no(
        "Did Hi Rokid complete a response?",
        default=True,
    )
    operator["visual_processing_indicated"] = ask_choice(
        "Did the app/glasses visibly or audibly indicate image capture or "
        "visual processing?",
        ("yes", "no", "unknown"),
        default="unknown",
    )
    operator["result_state"] = ask_choice(
        "What was the workflow result?",
        ("success", "error", "timeout", "unsupported", "unknown"),
        default="success",
    )
    operator["ui_or_audio_summary"] = prompt_text(
        "Enter a brief workflow/result summary. Do not evaluate accuracy.",
        default="",
    )
    operator["error_text"] = prompt_text(
        "Enter exact error text if any, otherwise leave blank.",
        default="",
    )
    if action == "context_followup":
        operator["operator_deliberately_reopened_camera"] = ask_yes_no(
            "Did you deliberately reopen a visual/camera entry before the "
            "follow-up?",
            default=False,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run connected-only Hi Rokid visual workflow discovery tests "
            "using iPad-displayed photos. This does not score answer accuracy."
        )
    )
    parser.add_argument(
        "--serial",
        help="ADB serial when multiple Android devices are connected.",
    )
    parser.add_argument(
        "--phases",
        help=(
            "Optional comma-separated phase IDs. Default: "
            "V0,V1,V2,V3,V4,V5."
        ),
    )
    parser.add_argument(
        "--include-offline",
        action="store_true",
        help="Append optional offline phase V6.",
    )
    parser.add_argument(
        "--photo-a",
        default="PHOTO-A",
        help="Operator label for the iPad photo used by V0-V3.",
    )
    parser.add_argument(
        "--photo-b",
        default="PHOTO-B",
        help="Operator label for the iPad photo used by V4-V5.",
    )
    parser.add_argument(
        "--photo-c",
        default="PHOTO-C",
        help="Operator label for the optional offline V6 photo.",
    )
    parser.add_argument(
        "--question",
        default=DEFAULT_VISION_QUESTION,
        help="Fixed visual question used by V2, V3, V4, and V6.",
    )
    parser.add_argument(
        "--followup-question",
        default=DEFAULT_FOLLOWUP_QUESTION,
        help="Fixed context-follow-up question used by V5.",
    )
    parser.add_argument(
        "--pull-new-phone-images",
        action="store_true",
        help=(
            "Privately pull newly created phone MediaStore image/video/audio "
            "candidates for each phase. Metadata is recorded regardless."
        ),
    )
    parser.add_argument(
        "--bugreport",
        action="store_true",
        help="Collect one Android bugreport after all selected phases.",
    )
    parser.add_argument(
        "--output",
        help=(
            "Custom output directory. Default: "
            "~/rokid-nettest/tests/15a-vision-workflow-<timestamp>"
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
        args.include_offline,
        args.phases,
    )
    validate_phase_dependencies(phase_ids)

    photos = {
        "A": args.photo_a,
        "B": args.photo_b,
        "C": args.photo_c,
    }

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (
            Path.home()
            / "rokid-nettest"
            / "tests"
            / f"15a-vision-workflow-{timestamp}"
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
                "model",
                "photo_id",
                "detail",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    write_checklist(
        root,
        phase_ids,
        photos,
        args.question,
        args.followup_question,
        args.pull_new_phone_images,
    )

    run_info: Dict[str, object] = {
        "schema": "rokid.test-run.v1",
        "test_id": "15a-vision-workflow-discovery",
        "scope": "workflow-not-accuracy",
        "start_utc": utc_now(),
        "output_directory": str(root),
        "hardware_policy": {
            "glasses_restart_allowed": False,
            "glasses_power_cycle_required": False,
            "hi_rokid_app_restart_allowed": True,
            "connected_only": True,
        },
        "visual_target": {
            "device": "iPad mini",
            "photo_a": photos["A"],
            "photo_b": photos["B"],
            "photo_c": photos["C"],
            "v2_v3_exact_same_photo_required": True,
            "accuracy_scoring": False,
        },
        "questions": {
            "visual_request": args.question,
            "context_followup": args.followup_question,
        },
        "device": device,
        "rokid_app": package_version(base, ROKID_PACKAGE),
        "pcapdroid_app": package_version(base, PCAPDROID_PACKAGE),
        "selected_phases": phase_ids,
        "pull_new_phone_images": args.pull_new_phone_images,
        "bugreport_requested": args.bugreport,
    }
    (root / "run-info-private.json").write_text(
        json.dumps(run_info, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nRokid Test 15A — Visual Workflow Discovery")
    print("==========================================")
    print("Scope:         workflow discovery; no accuracy scoring")
    print(f"Output:        {root}")
    print(f"Phone:         {device['manufacturer']} {device['model']}")
    print(f"Android user:  {user_id}")
    print(f"Phases:        {', '.join(phase_ids)}")
    print(f"PHOTO-A:       {photos['A']}")
    print(f"PHOTO-B:       {photos['B']}")
    print(f"PHOTO-C:       {photos['C']}")
    print("Glasses reset: NEVER performed by this script")

    prompt_enter(
        "Confirm the glasses are already powered on, connected, and stable. "
        "Confirm the iPad photos are stored locally and notifications, "
        "auto-lock, True Tone/Night Shift, and auto-brightness are disabled "
        "where practical. Do not restart or power-cycle the glasses."
    )

    system_dir = root / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    write_command_output(
        [*base, "shell", "dumpsys", "package", ROKID_PACKAGE],
        system_dir / "hi-rokid-package.txt",
    )
    write_command_output(
        [*base, "shell", "dumpsys", "package", PCAPDROID_PACKAGE],
        system_dir / "pcapdroid-package.txt",
    )
    collect_phase_system_state(base, system_dir, "before-run")

    phase_results: List[Dict[str, object]] = []

    for sequence, phase_id in enumerate(phase_ids, start=1):
        phase = PHASES[phase_id]
        phase_name = str(phase["name"])
        model = str(phase["model"])
        photo_id = photo_id_for_phase(phase, photos)
        phase_dir = root / "phases" / f"{sequence:02d}-{phase_id}-{phase_name}"
        phase_dir.mkdir(parents=True, exist_ok=False)

        print("\n" + "=" * 78)
        print(f"{phase_id}: {phase['title']}")
        print("=" * 78)
        print(f"Model:      {model}")
        print(f"iPad photo: {photo_id}")
        print(phase["instructions"])

        prompt_enter(
            f"Display `{photo_id}` full-screen on the iPad and confirm "
            f"`{model}` is selected when required. Confirm PCAPdroid is "
            "ready but not yet capturing."
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
                    "row_count": len(baseline_rows),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        collect_phase_system_state(base, phase_dir, "before")

        run([*base, "logcat", "-c"], check=False)
        logcat_process = start_logcat(
            base,
            phase_dir / "logcat-private.txt",
        )

        pulled_exports: List[Dict[str, object]] = []
        phone_media_candidates: List[Dict[str, str]] = []
        pulled_phone_media: List[Dict[str, object]] = []
        operator: Dict[str, object] = {
            "model": model,
            "photo_id": photo_id,
            "accuracy_scored": False,
            "question": (
                args.followup_question
                if phase["action"] == "context_followup"
                else args.question
            ),
        }

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
                model=model,
                photo_id=photo_id,
            )

            write_marker(
                marker_path,
                base,
                phase_id,
                "IPAD_TARGET_CONFIRMED",
                model=model,
                photo_id=photo_id,
            )

            if bool(phase["restart_app"]):
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_APP_RESTART_BEGIN",
                    model=model,
                    photo_id=photo_id,
                )
                restart_hi_rokid(base)
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_APP_RESTART_COMPLETE",
                    model=model,
                    photo_id=photo_id,
                )
            else:
                launch_package(base, ROKID_PACKAGE)
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_EXISTING_SESSION_REUSED",
                    model=model,
                    photo_id=photo_id,
                    detail=str(phase["preserve_session_from"]),
                )

            capture_screenshot(base, phase_dir / "before-action.png")
            capture_ui_xml(base, phase_dir / "before-action.xml")

            action = str(phase["action"])

            if action == "idle":
                countdown(
                    int(phase["wait_seconds"]),
                    str(phase["title"]),
                )
                operator["assistant_invoked"] = False

            elif action == "open_feature":
                prompt_enter(
                    "Open a visual-assistant, camera-analysis, or image "
                    "understanding entry point if one exists. Do not invoke "
                    "the assistant and do not ask a visual question. If no "
                    "separate entry exists, leave Hi Rokid on the normal "
                    "assistant screen."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "VISION_ENTRY_OPEN_ATTEMPT_COMPLETE",
                    model=model,
                    photo_id=photo_id,
                )
                operator["separate_visual_entry_available"] = ask_choice(
                    "Was a separate visual/camera-analysis entry available?",
                    ("yes", "no", "unknown"),
                    default="unknown",
                )
                operator["entry_description"] = prompt_text(
                    "Enter the page/control name, or describe why no separate "
                    "entry was available.",
                    default="",
                )
                operator["assistant_invoked"] = False
                countdown(
                    int(phase["wait_seconds"]),
                    str(phase["title"]),
                )

            elif action in {
                "vision_request",
                "offline_vision_request",
            }:
                if action == "offline_vision_request":
                    prompt_enter(
                        "Disable the phone's internet access while preserving "
                        "Bluetooth and the active glasses connection. Do not "
                        "disable or restart the glasses."
                    )
                    write_marker(
                        marker_path,
                        base,
                        phase_id,
                        "PHONE_INTERNET_DISABLED_OPERATOR",
                        model=model,
                        photo_id=photo_id,
                    )

                prompt_enter(
                    "Ready the exact visual request. After this Enter press, "
                    "do not touch the keyboard while speaking. Say the wake "
                    "phrase, wait for the listening cue, then ask exactly:\n\n"
                    f'    "{args.question}"\n\n'
                    "Wait for the complete response before returning to the "
                    "keyboard."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "VISION_REQUEST_ARMED",
                    model=model,
                    photo_id=photo_id,
                    detail=args.question,
                )
                prompt_enter(
                    "The visual request and response should now be complete."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "VISION_RESPONSE_WINDOW_COMPLETE",
                    model=model,
                    photo_id=photo_id,
                )

                operator["assistant_invoked"] = True
                operator["request_type"] = "visual"
                record_response_observation(
                    operator,
                    action=action,
                )

                if action == "offline_vision_request":
                    prompt_enter(
                        "Re-enable phone internet now while keeping the "
                        "glasses connected."
                    )
                    write_marker(
                        marker_path,
                        base,
                        phase_id,
                        "PHONE_INTERNET_REENABLED_OPERATOR",
                        model=model,
                        photo_id=photo_id,
                    )

            elif action == "context_followup":
                prompt_enter(
                    "Do not deliberately reopen a camera or visual feature. "
                    "After this Enter press, do not touch the keyboard while "
                    "speaking. Say the wake phrase, wait for the cue, then ask "
                    "exactly:\n\n"
                    f'    "{args.followup_question}"\n\n'
                    "Wait for the complete response before returning to the "
                    "keyboard."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "VISION_CONTEXT_FOLLOWUP_ARMED",
                    model=model,
                    photo_id=photo_id,
                    detail=args.followup_question,
                )
                prompt_enter(
                    "The context follow-up and response should now be complete."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "VISION_CONTEXT_FOLLOWUP_COMPLETE",
                    model=model,
                    photo_id=photo_id,
                )

                operator["assistant_invoked"] = True
                operator["request_type"] = "context_followup"
                record_response_observation(
                    operator,
                    action=action,
                )

            capture_screenshot(base, phase_dir / "after-action.png")
            capture_ui_xml(base, phase_dir / "after-action.xml")

            operator["selected_model_confirmed"] = ask_yes_no(
                f"Was `{model}` definitely selected for this phase?",
                default=True,
            )
            operator["displayed_photo_confirmed"] = ask_yes_no(
                f"Was `{photo_id}` definitely displayed for this phase?",
                default=True,
            )
            operator["operator_notes"] = prompt_text(
                "Enter any additional workflow notes, otherwise leave blank.",
                default="",
            )

            write_marker(
                marker_path,
                base,
                phase_id,
                "PHASE_ACTION_COMPLETE",
                model=model,
                photo_id=photo_id,
                detail=json.dumps(operator, separators=(",", ":")),
            )

            prompt_enter(
                "Stop PCAPdroid and export the raw PCAP/PCAPNG and SSL key "
                "log to Download/PCAPdroid. Export the connection CSV and "
                "other CSV/ZIP/JSON sidecars as well."
            )
            write_marker(
                marker_path,
                base,
                phase_id,
                "PCAP_CAPTURE_STOPPED_AND_EXPORTED",
                model=model,
                photo_id=photo_id,
            )

            (
                pulled_exports,
                current_rows,
                collection_uri,
            ) = pull_new_exports(
                base,
                user_id,
                collection_uri,
                baseline_ids,
                phase_start_epoch,
                phase_dir / "pcapdroid-export",
                f"{phase_id}-{phase_name}",
            )

            phone_media_candidates = new_phone_media_rows(
                current_rows,
                baseline_ids,
                phase_start_epoch,
            )

            if args.pull_new_phone_images and phone_media_candidates:
                pulled_phone_media = pull_phone_media_candidates(
                    base,
                    user_id,
                    collection_uri,
                    phone_media_candidates,
                    phase_dir / "phone-media-candidates-private",
                    f"{phase_id}-{phase_name}",
                )
        finally:
            stop_logcat(logcat_process)

        collect_phase_system_state(base, phase_dir, "after")

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

        (phase_dir / "pulled-media-private.json").write_text(
            json.dumps(pulled_exports, indent=2) + "\n",
            encoding="utf-8",
        )
        (phase_dir / "operator-observation-private.json").write_text(
            json.dumps(operator, indent=2) + "\n",
            encoding="utf-8",
        )
        (phase_dir / "new-phone-media-metadata-private.json").write_text(
            json.dumps(
                {
                    "captured_utc": utc_now(),
                    "candidate_count": len(phone_media_candidates),
                    "candidates": phone_media_candidates,
                    "pull_requested": args.pull_new_phone_images,
                    "pulled": pulled_phone_media,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        phase_gate = pcap_count >= 1 and keylog_count >= 1
        phase_result = {
            "sequence": sequence,
            "phase_id": phase_id,
            "phase_name": phase_name,
            "model": model,
            "photo_id": photo_id,
            "action": phase["action"],
            "restart_hi_rokid_app": bool(phase["restart_app"]),
            "preserve_session_from": phase["preserve_session_from"],
            "glasses_restart_performed": False,
            "accuracy_scored": False,
            "operator": operator,
            "pcap_count": pcap_count,
            "ssl_keylog_count": keylog_count,
            "sidecar_count": sidecar_count,
            "new_phone_media_candidate_count": len(
                phone_media_candidates
            ),
            "pulled_phone_media_count": len(pulled_phone_media),
            "evidence_gate_pass": phase_gate,
            "phase_directory": str(phase_dir),
            "pulled_exports": pulled_exports,
        }
        phase_results.append(phase_result)

        print(
            f"\n{phase_id} evidence: "
            f"{pcap_count} PCAP(s), "
            f"{keylog_count} SSL key log(s), "
            f"{sidecar_count} sidecar(s)"
        )
        print(
            f"{phase_id} new phone media candidates: "
            f"{len(phone_media_candidates)}"
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
            model=model,
            photo_id=photo_id,
            detail=json.dumps(
                {
                    "pcap_count": pcap_count,
                    "ssl_keylog_count": keylog_count,
                    "sidecar_count": sidecar_count,
                    "phone_media_candidates": len(
                        phone_media_candidates
                    ),
                    "gate_pass": phase_gate,
                },
                separators=(",", ":"),
            ),
        )

    bugreport_result: Dict[str, object] = {}
    if args.bugreport:
        bugreport_result = collect_bugreport(
            base,
            root / "system" / "bugreport-15a-vision-workflow.zip",
        )
        (root / "system" / "bugreport-result-private.json").write_text(
            json.dumps(bugreport_result, indent=2) + "\n",
            encoding="utf-8",
        )

    collect_phase_system_state(base, system_dir, "after-run")

    aggregate_pcap_count = sum(
        int(item["pcap_count"]) for item in phase_results
    )
    aggregate_keylog_count = sum(
        int(item["ssl_keylog_count"]) for item in phase_results
    )
    aggregate_sidecar_count = sum(
        int(item["sidecar_count"]) for item in phase_results
    )
    aggregate_phone_media_candidates = sum(
        int(item["new_phone_media_candidate_count"])
        for item in phase_results
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
        "aggregate_new_phone_media_candidate_count": (
            aggregate_phone_media_candidates
        ),
        "all_phase_gates_pass": all(
            bool(item["evidence_gate_pass"])
            for item in phase_results
        ),
        "aggregate_gate_pass": aggregate_gate,
        "accuracy_scored": False,
    }
    (root / "run-info-private.json").write_text(
        json.dumps(run_info, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = write_sha256_manifest(root)

    private_zip: Optional[Path] = None
    if args.zip:
        private_zip = make_private_zip(root)

    print("\nTest 15A evidence summary")
    print("=========================")
    print("Scope:                   visual workflow, not accuracy")
    print(f"Required phases:         {required}")
    print(f"Total PCAP files:        {aggregate_pcap_count}")
    print(f"Total SSL key logs:      {aggregate_keylog_count}")
    print(f"Total sidecars:          {aggregate_sidecar_count}")
    print(
        "Phone media candidates: "
        f"{aggregate_phone_media_candidates}"
    )
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
