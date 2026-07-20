#!/usr/bin/env python3
"""
Rokid Test 15B — visual routing, retention, and context persistence.

Purpose
-------
Resolve the secondary questions left by Test 15A:

1. Does an in-capture ChatGPT/Gemini selection change `vl_model_no`,
   `base_model_no`, or related visual-session parameters?
2. Can a grounded follow-up use a previously captured image without issuing
   another `take_photo` action?
3. Does Hi Rokid retain the visual-question thumbnail/history after the app is
   force-stopped and relaunched?
4. Is the retained thumbnail available while the phone is offline, or does
   reopening history require a cloud fetch?
5. Does the same behavior reproduce after switching in the opposite direction?

This is a functional workflow test, not a general vision-accuracy benchmark.

Hardware and safety policy
--------------------------
* The glasses must already be powered on, connected, and stable.
* The script NEVER restarts or power-cycles the glasses.
* Only the Hi Rokid PHONE APP may be force-stopped/relaunched.
* Bluetooth must remain enabled during every phase.
* Every phase receives a fresh PCAPdroid capture and SSL key-log export.
* All generated evidence is PRIVATE.

Default phases
--------------
B1  Capture Gemini -> ChatGPT selection and immediate Photo-A visual request.
B2  Same ChatGPT conversation: grounded follow-up, no deliberate recapture.
B3  Offline app-process restart: reopen ChatGPT conversation history.
B4  Online app-process restart: reopen the same ChatGPT conversation history.
B5  Capture ChatGPT -> Gemini selection and immediate Photo-B visual request.
B6  Same Gemini conversation: grounded follow-up, no deliberate recapture.

Target design
-------------
For each photo, choose one distinctive detail that the first answer is
instructed NOT to mention. The grounded follow-up then asks specifically about
that detail.

Example Photo A:
  Initial:  "Describe only the major objects. Do not identify the city or
             landmark shown on the screen."
  Follow-up: "Which landmark was visible on the tablet screen?"
  Expected:  "One World Trade Center"

Example Photo B:
  Initial:  "Describe only the major objects. Do not mention any times or
             numbers visible on the watches."
  Follow-up: "What time was shown on the round watch?"
  Expected:  "4:49"

A correct grounded answer with no new `take_photo`, no new image upload, and no
new thumbnail supports persistent visual context. An incorrect or non-grounded
answer does not invalidate routing/retention evidence; it leaves visual-context
persistence unconfirmed.

Example
-------
python3 run_15b_visual_routing_retention.py \
  --photo-a "A-skyline" \
  --chatgpt-initial-question \
    "Describe only the major objects. Do not identify the city or landmark shown on the screen." \
  --chatgpt-followup-question \
    "Which landmark was visible on the tablet screen?" \
  --chatgpt-expected-detail "One World Trade Center" \
  --photo-b "B-smartwatches" \
  --gemini-initial-question \
    "Describe only the major objects. Do not mention any times or numbers visible on the watches." \
  --gemini-followup-question \
    "What time was shown on the round watch?" \
  --gemini-expected-detail "4:49" \
  --bugreport \
  --zip

Privacy
-------
The output can contain packet captures, TLS secrets, screenshots, visual
conversation thumbnails, precise location/context, account/session data,
device identifiers, and Bluetooth HCI data. Do not commit the private evidence
directory or ZIP to a public repository.
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

DEFAULT_CHATGPT_INITIAL = (
    "Describe only the major objects in front of me. "
    "Do not mention text, numbers, times, city names, or landmarks."
)
DEFAULT_CHATGPT_FOLLOWUP = (
    "What distinctive detail did you leave out from the image?"
)
DEFAULT_GEMINI_INITIAL = DEFAULT_CHATGPT_INITIAL
DEFAULT_GEMINI_FOLLOWUP = DEFAULT_CHATGPT_FOLLOWUP


PHASES: Dict[str, Dict[str, object]] = {
    "B1": {
        "name": "switch-gemini-to-chatgpt-visual",
        "title": "Capture Gemini-to-ChatGPT selection and Photo-A visual request",
        "source_model": "Gemini",
        "target_model": "ChatGPT",
        "photo_key": "A",
        "action": "switch_and_visual",
        "preserve_session_from": "",
        "internet": "online",
    },
    "B2": {
        "name": "chatgpt-grounded-followup",
        "title": "ChatGPT grounded follow-up without deliberate recapture",
        "source_model": "ChatGPT",
        "target_model": "ChatGPT",
        "photo_key": "A",
        "action": "grounded_followup",
        "preserve_session_from": "B1",
        "internet": "online",
    },
    "B3": {
        "name": "offline-history-reopen",
        "title": "Offline process restart and ChatGPT history reopen",
        "source_model": "ChatGPT",
        "target_model": "ChatGPT",
        "photo_key": "A",
        "action": "offline_history_reopen",
        "preserve_session_from": "B1/B2",
        "internet": "offline",
    },
    "B4": {
        "name": "online-history-reopen",
        "title": "Online process restart and ChatGPT history reopen",
        "source_model": "ChatGPT",
        "target_model": "ChatGPT",
        "photo_key": "A",
        "action": "online_history_reopen",
        "preserve_session_from": "B1/B2",
        "internet": "online",
    },
    "B5": {
        "name": "switch-chatgpt-to-gemini-visual",
        "title": "Capture ChatGPT-to-Gemini selection and Photo-B visual request",
        "source_model": "ChatGPT",
        "target_model": "Gemini",
        "photo_key": "B",
        "action": "switch_and_visual",
        "preserve_session_from": "",
        "internet": "online",
    },
    "B6": {
        "name": "gemini-grounded-followup",
        "title": "Gemini grounded follow-up without deliberate recapture",
        "source_model": "Gemini",
        "target_model": "Gemini",
        "photo_key": "B",
        "action": "grounded_followup",
        "preserve_session_from": "B5",
        "internet": "online",
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
        existing_suffix = Path(
            strip_android_duplicate_suffix(original_name)
        ).suffix
        extension = existing_suffix or (
            mimetypes.guess_extension(row.get("mime_type", "")) or ""
        )
        destination_name = (
            f"{prefix}--{kind}--media-{media_id}--{safe_name}"
            if existing_suffix
            else (
                f"{prefix}--{kind}--media-{media_id}--"
                f"{safe_name}{extension}"
            )
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


def force_stop_and_launch_hi_rokid(base: Sequence[str]) -> None:
    adb_shell(
        base,
        "am",
        "force-stop",
        ROKID_PACKAGE,
        check=False,
    )
    time.sleep(1)
    launch_package(base, ROKID_PACKAGE)
    time.sleep(5)


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
    remote = "/sdcard/window_dump_15b.xml"
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


def collect_accessible_app_files(
    base: Sequence[str],
    destination: Path,
    suffix: str,
) -> None:
    shell_script = (
        "for d in "
        f"/sdcard/Android/data/{ROKID_PACKAGE} "
        f"/sdcard/Android/media/{ROKID_PACKAGE}; do "
        'echo "### $d"; '
        'if [ -e "$d" ]; then '
        'find "$d" -type f -exec ls -ln {} \\; 2>&1; '
        'else echo "NOT_PRESENT_OR_NOT_ACCESSIBLE"; fi; '
        "done"
    )
    write_command_output(
        [*base, "shell", "sh", "-c", shell_script],
        destination / f"accessible-app-files-{suffix}.txt",
    )


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
        f"netstats-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "netstats",
            "detail",
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
        f"package-{suffix}.txt": [
            *base,
            "shell",
            "dumpsys",
            "package",
            ROKID_PACKAGE,
        ],
    }

    for name, command in commands.items():
        write_command_output(command, destination / name)

    collect_accessible_app_files(base, destination, suffix)


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


def selected_phase_ids(requested: Optional[str]) -> List[str]:
    default_ids = ["B1", "B2", "B3", "B4", "B5", "B6"]
    if not requested:
        return default_ids

    parsed = [
        item.strip().upper()
        for item in requested.split(",")
        if item.strip()
    ]
    if not parsed:
        raise TestAbort("--phases did not contain any phase IDs.")

    seen: Set[str] = set()
    result: List[str] = []
    for phase_id in parsed:
        if phase_id not in PHASES:
            raise TestAbort(f"Unknown phase ID: {phase_id}")
        if phase_id in seen:
            raise TestAbort(f"Duplicate phase ID: {phase_id}")
        seen.add(phase_id)
        result.append(phase_id)
    return result


def validate_phase_dependencies(phase_ids: Sequence[str]) -> None:
    selected = set(phase_ids)
    dependencies = {
        "B2": "B1",
        "B3": "B1",
        "B4": "B1",
        "B6": "B5",
    }
    for phase_id, required in dependencies.items():
        if phase_id in selected and required not in selected:
            print(
                f"WARNING: {phase_id} is designed to follow {required}. "
                "Interpretation may be limited."
            )


def write_checklist(
    root: Path,
    phase_ids: Sequence[str],
    args: argparse.Namespace,
) -> None:
    lines = [
        "# Test 15B operator checklist",
        "",
        "## Scope",
        "",
        "Routing, conversation-image retention, and visual-context persistence. "
        "This is not a broad answer-quality benchmark.",
        "",
        "## Safety",
        "",
        "- Begin only after the glasses are powered on, connected, and stable.",
        "- Never restart or power-cycle the glasses during this test.",
        "- Only Hi Rokid on the phone may be force-stopped/relaunched.",
        "- Keep Bluetooth enabled in every phase.",
        "",
        "## Starting state",
        "",
        "- Before B1, ensure **Gemini** is selected.",
        "- Keep PHOTO-A ready on the iPad.",
        "- B1 captures the Gemini-to-ChatGPT switch inside the PCAP.",
        "- B5 captures the ChatGPT-to-Gemini switch inside the PCAP.",
        "",
        "## Targets and probes",
        "",
        f"- PHOTO-A: `{args.photo_a}`",
        f"- ChatGPT initial question: `{args.chatgpt_initial_question}`",
        f"- ChatGPT grounded follow-up: `{args.chatgpt_followup_question}`",
        f"- ChatGPT expected distinctive detail: "
        f"`{args.chatgpt_expected_detail or 'not supplied'}`",
        "",
        f"- PHOTO-B: `{args.photo_b}`",
        f"- Gemini initial question: `{args.gemini_initial_question}`",
        f"- Gemini grounded follow-up: `{args.gemini_followup_question}`",
        f"- Gemini expected distinctive detail: "
        f"`{args.gemini_expected_detail or 'not supplied'}`",
        "",
        "## PCAPdroid for every phase",
        "",
        "1. Start a fresh capture when instructed.",
        "2. Perform only the phase action.",
        "3. Stop the capture.",
        "4. Export PCAP/PCAPNG and SSL key log.",
        "5. Export connection CSV/ZIP/JSON sidecars.",
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


def observation_for_switch_visual(
    operator: Dict[str, object],
    source_model: str,
    target_model: str,
) -> None:
    operator["source_model_confirmed_before_switch"] = ask_yes_no(
        f"Was `{source_model}` selected immediately before the in-capture "
        f"switch?",
        default=True,
    )
    operator["target_model_confirmed_after_switch"] = ask_yes_no(
        f"Was `{target_model}` visibly selected after the switch?",
        default=True,
    )
    operator["response_completed"] = ask_yes_no(
        "Did the visual request complete with a response?",
        default=True,
    )
    operator["new_conversation_thumbnail_visible"] = ask_yes_no(
        "Did the new captured image appear as a thumbnail in Assistant "
        "conversation history?",
        default=True,
    )
    operator["workflow_result"] = ask_choice(
        "Visual workflow result",
        ("success", "error", "timeout", "unsupported", "unknown"),
        default="success",
    )
    operator["summary"] = prompt_text(
        "Enter a brief workflow summary. Do not score general answer quality.",
        default="",
    )


def observation_for_grounded_followup(
    operator: Dict[str, object],
    expected_detail: str,
) -> None:
    operator["response_completed"] = ask_yes_no(
        "Did the grounded follow-up complete with a response?",
        default=True,
    )
    operator["deliberately_reopened_camera"] = ask_yes_no(
        "Did you deliberately reopen a camera/visual feature before asking?",
        default=False,
    )
    operator["new_thumbnail_appeared"] = ask_yes_no(
        "Did a NEW image thumbnail appear for this follow-up?",
        default=False,
    )
    operator["answer_summary"] = prompt_text(
        "Enter the returned answer or a concise summary.",
        default="",
    )
    operator["expected_detail"] = expected_detail
    operator["grounding_classification"] = ask_choice(
        "Did the answer demonstrate the previously omitted distinctive detail?",
        ("confirmed", "not-confirmed", "incorrect", "unclear"),
        default="unclear",
    )


def observation_for_history_reopen(
    operator: Dict[str, object],
    offline: bool,
) -> None:
    operator["conversation_history_opened"] = ask_yes_no(
        "Were you able to reopen the prior ChatGPT conversation?",
        default=True,
    )
    operator["question_text_visible"] = ask_yes_no(
        "Was the prior visual question text visible?",
        default=True,
    )
    operator["answer_text_visible"] = ask_yes_no(
        "Was the prior assistant answer text visible?",
        default=True,
    )
    operator["image_thumbnail_visible"] = ask_yes_no(
        "Was the prior captured-image thumbnail visible?",
        default=True,
    )
    operator["thumbnail_loaded_without_placeholder"] = ask_yes_no(
        "Did the thumbnail render normally rather than as a blank/error "
        "placeholder?",
        default=True,
    )
    operator["loading_indicator_observed"] = ask_yes_no(
        "Did you observe a thumbnail/network loading indicator?",
        default=False,
    )
    operator["phone_internet_state"] = "offline" if offline else "online"
    operator["notes"] = prompt_text(
        "Enter any retention/loading observations.",
        default="",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Test 15B for Hi Rokid visual routing, conversation-image "
            "retention, and context persistence."
        )
    )
    parser.add_argument(
        "--serial",
        help="ADB serial when multiple Android devices are connected.",
    )
    parser.add_argument(
        "--phases",
        help="Optional comma-separated phase IDs. Default: B1-B6.",
    )
    parser.add_argument(
        "--photo-a",
        default="PHOTO-A",
        help="Label for the ChatGPT visual target.",
    )
    parser.add_argument(
        "--photo-b",
        default="PHOTO-B",
        help="Label for the Gemini visual target.",
    )
    parser.add_argument(
        "--chatgpt-initial-question",
        default=DEFAULT_CHATGPT_INITIAL,
        help="Initial ChatGPT visual question that omits the probe detail.",
    )
    parser.add_argument(
        "--chatgpt-followup-question",
        default=DEFAULT_CHATGPT_FOLLOWUP,
        help="Grounded ChatGPT follow-up about the omitted detail.",
    )
    parser.add_argument(
        "--chatgpt-expected-detail",
        default="",
        help="Expected distinctive detail for operator classification.",
    )
    parser.add_argument(
        "--gemini-initial-question",
        default=DEFAULT_GEMINI_INITIAL,
        help="Initial Gemini visual question that omits the probe detail.",
    )
    parser.add_argument(
        "--gemini-followup-question",
        default=DEFAULT_GEMINI_FOLLOWUP,
        help="Grounded Gemini follow-up about the omitted detail.",
    )
    parser.add_argument(
        "--gemini-expected-detail",
        default="",
        help="Expected distinctive detail for operator classification.",
    )
    parser.add_argument(
        "--pull-new-phone-images",
        action="store_true",
        help=(
            "Privately pull newly created phone MediaStore image/video/audio "
            "candidates. Metadata is always recorded."
        ),
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
            "~/rokid-nettest/tests/15b-visual-routing-retention-<timestamp>"
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

    phase_ids = selected_phase_ids(args.phases)
    validate_phase_dependencies(phase_ids)

    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (
            Path.home()
            / "rokid-nettest"
            / "tests"
            / f"15b-visual-routing-retention-{timestamp}"
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

    write_checklist(root, phase_ids, args)

    run_info: Dict[str, object] = {
        "schema": "rokid.test-run.v1",
        "test_id": "15b-visual-routing-retention-context",
        "scope": (
            "routing-retention-context-persistence-not-general-accuracy"
        ),
        "start_utc": utc_now(),
        "output_directory": str(root),
        "hardware_policy": {
            "glasses_restart_allowed": False,
            "glasses_power_cycle_required": False,
            "hi_rokid_app_restart_allowed": True,
            "bluetooth_must_remain_enabled": True,
            "connected_only": True,
        },
        "targets": {
            "photo_a": args.photo_a,
            "photo_b": args.photo_b,
        },
        "questions": {
            "chatgpt_initial": args.chatgpt_initial_question,
            "chatgpt_followup": args.chatgpt_followup_question,
            "chatgpt_expected_detail": args.chatgpt_expected_detail,
            "gemini_initial": args.gemini_initial_question,
            "gemini_followup": args.gemini_followup_question,
            "gemini_expected_detail": args.gemini_expected_detail,
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

    print("\nRokid Test 15B — Visual Routing, Retention, and Context")
    print("======================================================")
    print("Scope:         routing/retention/context; not broad accuracy")
    print(f"Output:        {root}")
    print(f"Phone:         {device['manufacturer']} {device['model']}")
    print(f"Android user:  {user_id}")
    print(f"Phases:        {', '.join(phase_ids)}")
    print(f"PHOTO-A:       {args.photo_a}")
    print(f"PHOTO-B:       {args.photo_b}")
    print("Glasses reset: NEVER performed by this script")

    prompt_enter(
        "Confirm the glasses are already powered on, connected, and stable. "
        "Confirm Gemini is currently selected before B1. Keep Bluetooth on "
        "throughout. Prepare PHOTO-A and PHOTO-B on the iPad. Do not restart "
        "or power-cycle the glasses."
    )

    system_dir = root / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    collect_phase_system_state(base, system_dir, "before-run")

    phase_results: List[Dict[str, object]] = []

    for sequence, phase_id in enumerate(phase_ids, start=1):
        phase = PHASES[phase_id]
        phase_name = str(phase["name"])
        source_model = str(phase["source_model"])
        target_model = str(phase["target_model"])
        photo_id = (
            args.photo_a
            if str(phase["photo_key"]) == "A"
            else args.photo_b
        )
        phase_dir = root / "phases" / f"{sequence:02d}-{phase_id}-{phase_name}"
        phase_dir.mkdir(parents=True, exist_ok=False)

        print("\n" + "=" * 80)
        print(f"{phase_id}: {phase['title']}")
        print("=" * 80)
        print(f"Source model: {source_model}")
        print(f"Target model: {target_model}")
        print(f"iPad photo:   {photo_id}")
        print(f"Internet:     {phase['internet']}")

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
            "source_model": source_model,
            "target_model": target_model,
            "photo_id": photo_id,
            "action": phase["action"],
            "accuracy_benchmark": False,
        }

        try:
            launch_package(base, PCAPDROID_PACKAGE)
            prompt_enter(
                "Start a fresh PCAPdroid capture for Hi Rokid. Confirm the "
                "capture timer or notification is active."
            )
            write_marker(
                marker_path,
                base,
                phase_id,
                "PCAP_CAPTURE_STARTED",
                model=target_model,
                photo_id=photo_id,
            )

            action = str(phase["action"])

            if action == "switch_and_visual":
                initial_question = (
                    args.chatgpt_initial_question
                    if target_model == "ChatGPT"
                    else args.gemini_initial_question
                )

                prompt_enter(
                    f"Confirm `{source_model}` is selected NOW and "
                    f"`{photo_id}` is displayed full-screen. While this "
                    "capture remains active:\n\n"
                    f"1. Open Hi Rokid's model selector.\n"
                    f"2. Switch from {source_model} to {target_model}.\n"
                    "3. Wait for the selection to complete.\n"
                    "4. Tap the + control to start a fresh assistant "
                    "conversation if available.\n"
                    "5. Return here without asking the question yet."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "MODEL_SWITCH_COMPLETE",
                    model=target_model,
                    photo_id=photo_id,
                    detail=f"{source_model}->{target_model}",
                )
                capture_screenshot(
                    base,
                    phase_dir / "after-model-switch.png",
                )
                capture_ui_xml(
                    base,
                    phase_dir / "after-model-switch.xml",
                )

                prompt_enter(
                    "Ready the visual request. After this Enter press, do not "
                    "touch the keyboard while speaking. Say the wake phrase, "
                    "wait for the cue, then ask exactly:\n\n"
                    f'    "{initial_question}"\n\n'
                    "Wait for the full response and thumbnail before "
                    "returning to the keyboard."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "VISUAL_REQUEST_ARMED",
                    model=target_model,
                    photo_id=photo_id,
                    detail=initial_question,
                )
                prompt_enter(
                    "The visual request, response, and thumbnail should now "
                    "be complete."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "VISUAL_RESPONSE_COMPLETE",
                    model=target_model,
                    photo_id=photo_id,
                )
                capture_screenshot(
                    base,
                    phase_dir / "after-visual-response.png",
                )
                capture_ui_xml(
                    base,
                    phase_dir / "after-visual-response.xml",
                )
                operator["question"] = initial_question
                observation_for_switch_visual(
                    operator,
                    source_model,
                    target_model,
                )

            elif action == "grounded_followup":
                followup = (
                    args.chatgpt_followup_question
                    if target_model == "ChatGPT"
                    else args.gemini_followup_question
                )
                expected = (
                    args.chatgpt_expected_detail
                    if target_model == "ChatGPT"
                    else args.gemini_expected_detail
                )

                prompt_enter(
                    f"Keep the SAME `{target_model}` conversation from "
                    f"`{phase['preserve_session_from']}` open. Do not tap +, "
                    "do not reopen a camera feature, and do not deliberately "
                    "request a new photo. After this Enter press, say the wake "
                    "phrase, wait for the cue, then ask exactly:\n\n"
                    f'    "{followup}"\n\n'
                    "Wait for the complete response."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "GROUNDED_FOLLOWUP_ARMED",
                    model=target_model,
                    photo_id=photo_id,
                    detail=followup,
                )
                prompt_enter(
                    "The grounded follow-up response should now be complete."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "GROUNDED_FOLLOWUP_COMPLETE",
                    model=target_model,
                    photo_id=photo_id,
                )
                capture_screenshot(
                    base,
                    phase_dir / "after-grounded-followup.png",
                )
                capture_ui_xml(
                    base,
                    phase_dir / "after-grounded-followup.xml",
                )
                operator["question"] = followup
                observation_for_grounded_followup(
                    operator,
                    expected,
                )

            elif action == "offline_history_reopen":
                prompt_enter(
                    "Disable the PHONE'S internet access while preserving "
                    "Bluetooth and the glasses connection. Confirm Wi-Fi and "
                    "mobile data are unavailable, but Bluetooth remains on."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "PHONE_INTERNET_DISABLED_OPERATOR",
                    model=target_model,
                    photo_id=photo_id,
                )
                collect_phase_system_state(
                    base,
                    phase_dir,
                    "offline-before-restart",
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_FORCE_STOP_RELAUNCH_BEGIN",
                    model=target_model,
                    photo_id=photo_id,
                )
                force_stop_and_launch_hi_rokid(base)
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_FORCE_STOP_RELAUNCH_COMPLETE",
                    model=target_model,
                    photo_id=photo_id,
                )
                prompt_enter(
                    "With the phone still offline, reopen the prior ChatGPT "
                    "conversation containing PHOTO-A. Wait up to 30 seconds "
                    "for text and thumbnail rendering. Do not ask a new "
                    "assistant question."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "OFFLINE_HISTORY_REOPEN_OBSERVED",
                    model=target_model,
                    photo_id=photo_id,
                )
                capture_screenshot(
                    base,
                    phase_dir / "offline-history-reopen.png",
                )
                capture_ui_xml(
                    base,
                    phase_dir / "offline-history-reopen.xml",
                )
                observation_for_history_reopen(operator, offline=True)

                prompt_enter(
                    "Re-enable the phone's internet now while preserving the "
                    "glasses connection."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "PHONE_INTERNET_REENABLED_OPERATOR",
                    model=target_model,
                    photo_id=photo_id,
                )

            elif action == "online_history_reopen":
                prompt_enter(
                    "Confirm phone internet is ON and Bluetooth/glasses remain "
                    "connected. The script will force-stop and relaunch only "
                    "Hi Rokid."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_FORCE_STOP_RELAUNCH_BEGIN",
                    model=target_model,
                    photo_id=photo_id,
                )
                force_stop_and_launch_hi_rokid(base)
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "HI_ROKID_FORCE_STOP_RELAUNCH_COMPLETE",
                    model=target_model,
                    photo_id=photo_id,
                )
                prompt_enter(
                    "Reopen the same prior ChatGPT conversation containing "
                    "PHOTO-A. Wait up to 30 seconds and observe whether the "
                    "thumbnail loads immediately, after a network delay, or "
                    "not at all. Do not ask a new question."
                )
                write_marker(
                    marker_path,
                    base,
                    phase_id,
                    "ONLINE_HISTORY_REOPEN_OBSERVED",
                    model=target_model,
                    photo_id=photo_id,
                )
                capture_screenshot(
                    base,
                    phase_dir / "online-history-reopen.png",
                )
                capture_ui_xml(
                    base,
                    phase_dir / "online-history-reopen.xml",
                )
                observation_for_history_reopen(operator, offline=False)

            else:
                raise TestAbort(f"Unsupported phase action: {action}")

            operator["additional_notes"] = prompt_text(
                "Enter any additional phase notes, otherwise leave blank.",
                default="",
            )
            write_marker(
                marker_path,
                base,
                phase_id,
                "PHASE_ACTION_COMPLETE",
                model=target_model,
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
                model=target_model,
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
            "source_model": source_model,
            "target_model": target_model,
            "photo_id": photo_id,
            "action": phase["action"],
            "internet_state": phase["internet"],
            "preserve_session_from": phase["preserve_session_from"],
            "glasses_restart_performed": False,
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
            model=target_model,
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
            root / "system" / "bugreport-15b-visual-routing-retention.zip",
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
        "general_accuracy_benchmark": False,
    }
    (root / "run-info-private.json").write_text(
        json.dumps(run_info, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = write_sha256_manifest(root)

    private_zip: Optional[Path] = None
    if args.zip:
        private_zip = make_private_zip(root)

    print("\nTest 15B evidence summary")
    print("=========================")
    print("Scope:                   routing, retention, context persistence")
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
