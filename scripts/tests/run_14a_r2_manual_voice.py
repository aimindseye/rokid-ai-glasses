#!/usr/bin/env python3
"""
Rokid Test 14A-r2 — controlled ChatGPT/Gemini base-model comparison.

Runs on macOS with an ADB-connected Samsung Galaxy S25. The script is
interactive because PCAPdroid capture/export and Hi Rokid model selection are
performed on the phone.

Key properties:
  * Displays the wake phrase and one fixed question for every trial.
  * Uses one pre-wake Enter press; no Enter is required during speech.
  * Derives question-end and LLM timing from decrypted network events.
  * Rejects and retries attempts whose recognized prompt is not correct.
  * Alternates model order to reduce time/order bias.
  * Force-stops and relaunches Hi Rokid before every prompt attempt.
  * Takes a MediaStore baseline before each capture.
  * Pulls only newly-created PCAPdroid exports via `content read`.
  * Never uses `adb shell find` or a shell-side `>=` MediaStore expression.
  * Collects logcat, screenshots, UI XML, event markers, and SHA-256 hashes.

Default qualification matrix:
  3 prompts x 3 paired repetitions x 2 models = 18 accepted captures.
  Rejected ASR attempts are retained separately and retried.

Examples:
  python3 run_14a_r2.py
  python3 run_14a_r2.py --repeats 1
  python3 run_14a_r2.py --output ~/rokid-nettest/tests/14a-r2
  python3 run_14a_r2.py --serial ANDROID_SERIAL
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
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
PULL_SUFFIXES = PCAP_SUFFIXES + SIDECAR_SUFFIXES
SSL_KEYLOG_TOKENS = (
    "sslkeylog",
    "ssl-keylog",
    "ssl_keylog",
    "keylogfile",
    "tlskeylog",
)


def strip_android_duplicate_suffix(name: str) -> str:
    """Convert names such as `sslkeylogfile.txt (18)` to the logical name."""
    return re.sub(r"\s*\(\d+\)$", "", name.strip().lower())


def has_logical_suffix(name: str, suffixes: Sequence[str]) -> bool:
    return strip_android_duplicate_suffix(name).endswith(tuple(suffixes))


def is_pcap_name(name: str) -> bool:
    return has_logical_suffix(name, PCAP_SUFFIXES)


def is_ssl_keylog_name(name: str) -> bool:
    lowered = strip_android_duplicate_suffix(name)
    return any(token in lowered for token in SSL_KEYLOG_TOKENS)


PROMPTS: Sequence[Tuple[str, str, str]] = (
    (
        "P1",
        "reasoning",
        (
            "The original price is eighty dollars. "
            "It is discounted by twenty-five percent, then eight percent "
            "sales tax is added. Answer with only the final dollar amount."
        ),
    ),
    (
        "P2",
        "explanation",
        (
            "Explain why a metal spoon feels colder than a wooden spoon. "
            "Use exactly three sentences."
        ),
    ),
    (
        "P3",
        "format-control",
        (
            "Name three differences between Bluetooth Low Energy and "
            "Bluetooth Classic. Use exactly three numbered lines."
        ),
    ),
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
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    return cmd


def adb_shell(
    base: Sequence[str],
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess:
    # Passing arguments separately avoids local-shell parsing.
    return run([*base, "shell", *args], check=check)


def prompt_enter(message: str) -> None:
    try:
        input(f"\n{message}\nPress Enter to continue... ")
    except (EOFError, KeyboardInterrupt) as exc:
        raise TestAbort("User aborted the test.") from exc


def ask_yes_no(message: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"{message} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt) as exc:
        raise TestAbort("User aborted the test.") from exc

    if not answer:
        return default
    return answer in {"y", "yes"}


def sanitize_component(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return value.strip("-") or "unnamed"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def local_now() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def phone_epoch(base: Sequence[str]) -> str:
    result = adb_shell(base, "date", "+%s", check=False)
    value = result.stdout.strip()
    return value if value.isdigit() else ""


def phone_time(base: Sequence[str]) -> str:
    result = adb_shell(base, "date", "+%Y-%m-%dT%H:%M:%S%z", check=False)
    return result.stdout.strip()


def write_marker(
    marker_path: Path,
    base: Sequence[str],
    label: str,
    *,
    model: str = "",
    prompt_id: str = "",
    repetition: int = 0,
    attempt: int = 0,
    detail: str = "",
) -> None:
    fields = [
        utc_now(),
        local_now(),
        phone_epoch(base),
        phone_time(base),
        label,
        model,
        prompt_id,
        str(repetition or ""),
        str(attempt or ""),
        detail.replace("\t", " ").replace("\n", " "),
    ]
    with marker_path.open("a", encoding="utf-8") as handle:
        handle.write("\t".join(fields) + "\n")


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

    serial_result = run([*base, "get-serialno"], check=False)
    user_result = adb_shell(base, "am", "get-current-user", check=False)

    return {
        "serial": serial_result.stdout.strip(),
        "current_user": user_result.stdout.strip() or "0",
        "manufacturer": prop("ro.product.manufacturer"),
        "model": prop("ro.product.model"),
        "device": prop("ro.product.device"),
        "android_release": prop("ro.build.version.release"),
        "sdk": prop("ro.build.version.sdk"),
        "build_fingerprint": prop("ro.build.fingerprint"),
    }


def package_version(base: Sequence[str], package: str) -> Dict[str, str]:
    result = adb_shell(base, "dumpsys", "package", package, check=False)
    text = result.stdout

    def first(pattern: str) -> str:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    return {
        "package": package,
        "version_name": first(r"\bversionName=([^\s]+)"),
        "version_code": first(r"\bversionCode=(\d+)"),
        "first_install_time": first(r"\bfirstInstallTime=(.+)"),
        "last_update_time": first(r"\blastUpdateTime=(.+)"),
    }


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
    """
    Query the MediaStore file table without a WHERE comparison.

    Some Samsung/Android shells interpret >= as output redirection before
    `content query` receives it. Filtering is therefore done locally.
    """
    failures: List[str] = []

    for volume in ("external_primary", "external"):
        collection_uri = f"content://media/{volume}/file"
        result = adb_shell(
            base,
            "content",
            "query",
            "--user",
            user_id,
            "--uri",
            collection_uri,
            "--projection",
            MEDIA_PROJECTION,
            check=False,
        )
        combined = (result.stdout + "\n" + result.stderr).strip()

        if result.returncode == 0 and "Exception" not in combined:
            return collection_uri, parse_content_rows(result.stdout)

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
    path = row.get("relative_path", "")
    lowered_name = strip_android_duplicate_suffix(name)
    lowered_path = path.lower()

    pcap_match = is_pcap_name(name)
    ssl_keylog_match = is_ssl_keylog_name(name)
    sidecar_match = has_logical_suffix(name, SIDECAR_SUFFIXES)
    pcapdroid_path = "pcapdroid" in lowered_path
    pcapdroid_name = "pcapdroid" in lowered_name

    # SSL key logs are often exported to Download with duplicate names such
    # as `sslkeylogfile.txt (18)`, so they must not depend on folder matching.
    return (
        pcap_match
        or ssl_keylog_match
        or (sidecar_match and (pcapdroid_path or pcapdroid_name))
    )


def new_media_rows(
    rows: Iterable[Dict[str, str]],
    baseline_ids: Set[str],
    capture_start_epoch: int,
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

        # Allow a small clock/indexing tolerance.
        if changed and changed < capture_start_epoch - 120:
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
    item_uri: str,
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
                item_uri,
            ],
            stdout=output,
            stderr=subprocess.PIPE,
            check=False,
        )

    if process.returncode != 0:
        partial.unlink(missing_ok=True)
        error = process.stderr.decode("utf-8", errors="replace").strip()
        raise TestAbort(
            f"MediaStore read failed for {item_uri}: "
            + (error or f"exit {process.returncode}")
        )

    partial.replace(destination)


def pull_new_exports(
    base: Sequence[str],
    user_id: str,
    collection_uri: str,
    baseline_ids: Set[str],
    capture_start_epoch: int,
    destination_dir: Path,
    prefix: str,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, str]] = []

    # MediaStore indexing can lag behind the export completion.
    for _ in range(5):
        current_uri, current_rows = query_media_store(base, user_id)
        collection_uri = current_uri
        rows = new_media_rows(
            current_rows,
            baseline_ids,
            capture_start_epoch,
        )
        if any(
            is_pcap_name(row.get("_display_name", ""))
            for row in rows
        ):
            break
        time.sleep(2)

    if not rows:
        return []

    pulled: List[Dict[str, object]] = []

    for row in rows:
        media_id = row["_id"]
        original_name = row.get(
            "_display_name",
            f"media-{media_id}",
        )
        safe_original = sanitize_component(original_name)
        destination = destination_dir / f"{prefix}--{safe_original}"

        if destination.exists():
            destination = destination_dir / (
                f"{prefix}--media-{media_id}--{safe_original}"
            )

        item_uri = f"{collection_uri}/{media_id}"
        content_read_to_file(
            base,
            user_id,
            item_uri,
            destination,
        )

        actual_size = destination.stat().st_size
        expected_size = to_int(row.get("_size"))

        pulled.append(
            {
                "media_id": media_id,
                "uri": item_uri,
                "original_name": original_name,
                "relative_path": row.get("relative_path", ""),
                "mime_type": row.get("mime_type", ""),
                "reported_size": expected_size,
                "actual_size": actual_size,
                "destination": str(destination),
                "sha256": sha256_file(destination),
                "size_matches": (
                    expected_size <= 0 or expected_size == actual_size
                ),
            }
        )

    return pulled


def start_logcat(base: Sequence[str], destination: Path) -> subprocess.Popen:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = destination.open("wb")
    process = subprocess.Popen(
        [*base, "logcat", "-v", "threadtime"],
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    # Keep the handle attached so it can be closed later.
    process._output_handle = handle  # type: ignore[attr-defined]
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
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = run(
        [*base, "exec-out", "screencap", "-p"],
        check=False,
        text=False,
    )
    if result.returncode == 0 and result.stdout:
        destination.write_bytes(result.stdout)


def capture_ui_xml(base: Sequence[str], destination: Path) -> None:
    remote = "/sdcard/window_dump_14a_r2.xml"
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


def launch_package(base: Sequence[str], package: str) -> None:
    result = adb_shell(
        base,
        "monkey",
        "-p",
        package,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
        check=False,
    )
    if result.returncode != 0:
        print(
            f"WARNING: could not launch {package}: "
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )


def fresh_rokid_session(base: Sequence[str]) -> None:
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


def prepare_prompt_suite() -> List[Dict[str, str]]:
    """Return the fixed wording that the wearer must speak."""
    return [
        {
            "prompt_id": prompt_id,
            "category": category,
            "text": text,
            "input_mode": "wearer_manual_voice",
            "timing_mode": "network_events_authoritative",
        }
        for prompt_id, category, text in PROMPTS
    ]


def arm_wake_and_question(
    prompt_entry: Dict[str, str],
    wake_phrase: str,
) -> None:
    """
    Display the exact spoken sequence and wait for one pre-wake arm press.

    After pressing Enter, the wearer immediately says the wake phrase, waits
    for the glasses' listening cue, and then speaks the exact question. There
    is deliberately no keyboard interaction while speaking. Question-end and
    response latency are derived later from decrypted `recognized_speech` and
    `llm` WebSocket events.
    """
    print("\n" + "=" * 76)
    print(f"WAKE + QUESTION SEQUENCE FOR {prompt_entry['prompt_id']}")
    print("=" * 76)
    print(f"Wake phrase: {wake_phrase}")
    print()
    print("Question:")
    print(prompt_entry["text"])
    print("=" * 76)
    print(
        "After pressing Enter:\n"
        f"  1. Immediately say: {wake_phrase}\n"
        "  2. Wait for the assistant listening cue.\n"
        "  3. Speak the exact question shown above.\n"
        "  4. Do not touch the keyboard while speaking.\n"
        "  5. Press Enter again only after the full response and TTS finish."
    )
    prompt_enter(
        "Press Enter once to arm the wake-and-question sequence."
    )



def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256sums(root: Path) -> Path:
    output = root / "SHA256SUMS-private.txt"
    lines: List[str] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path == output:
            continue
        if path.suffix == ".partial":
            continue
        lines.append(f"{sha256_file(path)}  {path.relative_to(root)}")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


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


def schedule_for(repeats: int) -> List[Tuple[str, str, int]]:
    """
    Pair models closely and alternate which model runs first.

    For repetition 1: CHATGPT then GEMINI
    For repetition 2: GEMINI then CHATGPT
    For repetition 3: CHATGPT then GEMINI
    """
    schedule: List[Tuple[str, str, int]] = []
    for prompt_id, _, _ in PROMPTS:
        for repetition in range(1, repeats + 1):
            order = (
                ("CHATGPT", "GEMINI")
                if repetition % 2 == 1
                else ("GEMINI", "CHATGPT")
            )
            for model in order:
                schedule.append((model, prompt_id, repetition))
    return schedule


def prompt_lookup(
    generated_prompts: Sequence[Dict[str, str]],
    prompt_id: str,
) -> Dict[str, str]:
    for entry in generated_prompts:
        if entry["prompt_id"] == prompt_id:
            return entry
    raise KeyError(prompt_id)


def write_checklist(
    root: Path,
    repeats: int,
    max_attempts: int,
) -> None:
    text = f"""# Test 14A-r2 manual-voice operator checklist

This directory contains **private evidence**.

## Preconditions

- Galaxy S25 connected and authorized through ADB.
- Rokid AI Glasses connected to Hi Rokid.
- PCAPdroid MITM certificate/configuration working.
- PCAPdroid capture restricted to Hi Rokid where practical.
- SSL key logging/decryption export enabled.
- The wearer will speak the wake phrase and every question directly to the glasses.
- Use the same speaking position, pace, and volume for both model selections.
- Use the configured wake phrase only to invoke the assistant; then speak the
  exact displayed question after the listening cue.
- Do not paraphrase or add words to the question.

## Matrix

- Models: ChatGPT and Gemini
- Prompts: P1, P2, P3
- Accepted paired repetitions per prompt: {repeats}
- Required accepted captures: {repeats * len(PROMPTS) * 2}
- Maximum attempts per qualification slot: {max_attempts}

The script alternates model order and force-stops/relaunches Hi Rokid before
every attempt. One Enter press arms the wake-and-question sequence. No Enter
is required while speaking. A prompt-recognition mismatch is retained as
rejected evidence and the same slot is attempted again.

## Acceptance rule

Answer **yes** to the ASR acceptance question only when the displayed or
otherwise observable recognized request contains the intended meaning and all
critical constraints:

- P1 must include original price 80, 25 percent discount, 8 percent tax, and
  dollar-only output.
- P2 must request the metal-versus-wooden-spoon explanation and exactly three
  sentences.
- P3 must request BLE versus Bluetooth Classic and exactly three numbered
  lines.

Packet analysis remains authoritative and may later reject an operator-accepted
attempt if the decrypted `recognized_speech` differs materially. Question-end,
first-text, and complete-text timing are derived from WebSocket events rather
than a manual post-speech key press.

## PCAPdroid export requirement

After each attempt, including rejected attempts:

1. Stop the capture.
2. Export the raw PCAP/PCAPNG to `Download/PCAPdroid`.
3. Export the SSL key log or a PCAPdroid archive containing it to the same
   MediaStore-visible folder.
4. Return here and press Enter.

The script pulls only MediaStore records created after that attempt's baseline.
"""
    (root / "operator-checklist.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run controlled Rokid Test 14A-r2 and pull new PCAPdroid "
            "exports through Android MediaStore."
        )
    )
    parser.add_argument(
        "--serial",
        help="ADB serial when more than one device is connected.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Paired repetitions per prompt; default: 3.",
    )
    parser.add_argument(
        "--wake-phrase",
        default="Hi Rokid",
        help='Wake phrase spoken before each question; default: "Hi Rokid".',
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help=(
            "Maximum spoken/ASR attempts per model-prompt repetition; "
            "default: 3."
        ),
    )
    parser.add_argument(
        "--output",
        help=(
            "Output directory. Default: "
            "~/rokid-nettest/14a-r2-ai-assistant-base-model-<timestamp>"
        ),
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Create a private evidence ZIP at the end.",
    )
    args = parser.parse_args()

    if args.repeats <= 0:
        parser.error("--repeats must be greater than zero")
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be greater than zero")

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
            / f"14a-r2-manual-voice-base-model-{timestamp}"
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
                "label",
                "model",
                "prompt_id",
                "repetition",
                "attempt",
                "detail",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    write_checklist(root, args.repeats, args.max_attempts)
    generated_prompts = prepare_prompt_suite()
    (root / "prompt-suite.json").write_text(
        json.dumps(generated_prompts, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "prompt-suite.txt").write_text(
        "\n\n".join(
            f"{entry['prompt_id']} {entry['category']}\n{entry['text']}"
            for entry in generated_prompts
        )
        + "\n",
        encoding="utf-8",
    )

    run_info = {
        "test_id": "14a-r2-ai-assistant-base-model",
        "privacy": "PRIVATE_RAW_PCAP_LOGCAT_SCREENSHOTS",
        "start_utc": utc_now(),
        "output_directory": str(root),
        "device": device,
        "rokid_app": package_version(base, ROKID_PACKAGE),
        "pcapdroid_app": package_version(base, PCAPDROID_PACKAGE),
        "input_mode": "wearer_manual_voice",
        "wake_phrase": args.wake_phrase,
        "timing_policy": {
            "manual_marker": "WAKE_AND_QUESTION_ARMED",
            "question_end": "derive_from_final_recognized_speech",
            "first_text": "derive_from_first_llm_text_event",
            "complete_text": "derive_from_final_llm_text_event",
            "tts_complete": "operator_response_complete_marker_only",
        },
        "repeats": args.repeats,
        "max_attempts_per_slot": args.max_attempts,
        "required_accepted_captures": args.repeats * len(PROMPTS) * 2,
        "maximum_possible_attempt_captures": (
            args.repeats * len(PROMPTS) * 2 * args.max_attempts
        ),
        "schedule": [
            {
                "model": model,
                "prompt_id": prompt_id,
                "repetition": repetition,
            }
            for model, prompt_id, repetition in schedule_for(args.repeats)
        ],
    }
    (root / "run-info-private.json").write_text(
        json.dumps(run_info, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nRokid Test 14A-r2")
    print("==================")
    print(f"Output:       {root}")
    print(f"ADB serial:   {device['serial']}")
    print(f"Phone:        {device['manufacturer']} {device['model']}")
    print(f"Android user: {user_id}")
    print(
        f"Accepted slots: "
        f"{run_info['required_accepted_captures']}"
    )
    print(
        f"Max attempts:   "
        f"{run_info['maximum_possible_attempt_captures']}"
    )
    print("Input mode:     wearer speaks directly to glasses")
    print(f"Wake phrase:    {args.wake_phrase}")
    print("Timing:         decrypted network events are authoritative")
    print()
    print(
        "The output contains private traffic and device/account evidence. "
        "Do not publish it without sanitization."
    )

    prompt_enter(
        "Confirm the glasses are connected, Hi Rokid is logged in, and "
        "PCAPdroid MITM/SSL-key export is ready."
    )
    write_marker(marker_path, base, "TEST_START")

    results: List[Dict[str, object]] = []
    schedule = schedule_for(args.repeats)

    accepted_slots = 0
    failed_slots: List[Dict[str, object]] = []

    for index, (model, prompt_id, repetition) in enumerate(schedule, start=1):
        prompt_entry = prompt_lookup(generated_prompts, prompt_id)
        slot_accepted = False

        for attempt in range(1, args.max_attempts + 1):
            run_label = (
                f"{index:02d}-{model}-{prompt_id}-"
                f"R{repetition:02d}-A{attempt:02d}"
            )
            run_dir = root / "runs" / run_label
            run_dir.mkdir(parents=True, exist_ok=False)

            print("\n" + "=" * 76)
            print(
                f"Qualification slot {index}/{len(schedule)}: "
                f"{model} / {prompt_id} / repetition {repetition}"
            )
            print(f"Attempt {attempt}/{args.max_attempts}")
            print("=" * 76)
            print(prompt_entry["text"])

            launch_package(base, ROKID_PACKAGE)
            prompt_enter(
                f"In Hi Rokid, select the {model} base model. "
                "Verify the selection is visibly active."
            )
            write_marker(
                marker_path,
                base,
                "MODEL_SELECTED",
                model=model,
                prompt_id=prompt_id,
                repetition=repetition,
                attempt=attempt,
            )
            capture_screenshot(
                base,
                run_dir / "model-selected.png",
            )
            capture_ui_xml(
                base,
                run_dir / "model-selected.xml",
            )

            collection_uri, baseline_rows = query_media_store(base, user_id)
            baseline_ids = media_ids(baseline_rows)
            capture_start_epoch = int(time.time())

            (run_dir / "media-baseline-private.json").write_text(
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
            logcat_process: Optional[subprocess.Popen] = start_logcat(
                base,
                run_dir / "logcat-private.txt",
            )

            asr_operator_match = False
            pulled: List[Dict[str, object]] = []
            pcap_count = 0
            ssl_keylog_count = 0

            try:
                launch_package(base, PCAPDROID_PACKAGE)
                prompt_enter(
                    "In PCAPdroid, start a new capture for Hi Rokid. "
                    "Confirm the capture timer/notification is active."
                )
                write_marker(
                    marker_path,
                    base,
                    "PCAP_CAPTURE_STARTED",
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                )

                fresh_rokid_session(base)
                write_marker(
                    marker_path,
                    base,
                    "HI_ROKID_RELAUNCHED",
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                )

                arm_wake_and_question(
                    prompt_entry,
                    args.wake_phrase,
                )
                wake_question_detail = json.dumps(
                    {
                        "wake_phrase": args.wake_phrase,
                        "question": prompt_entry["text"],
                        "instruction": (
                            "say wake phrase immediately; wait for listening "
                            "cue; speak exact question"
                        ),
                    },
                    separators=(",", ":"),
                )
                write_marker(
                    marker_path,
                    base,
                    "WAKE_AND_QUESTION_ARMED",
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                    detail=wake_question_detail,
                )
                write_marker(
                    marker_path,
                    base,
                    "EXPECTED_WAKE_PHRASE",
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                    detail=args.wake_phrase,
                )
                write_marker(
                    marker_path,
                    base,
                    "EXPECTED_QUESTION",
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                    detail=prompt_entry["text"],
                )

                prompt_enter(
                    "Do not press Enter while invoking or asking the question. "
                    "Press Enter now only after the complete assistant response "
                    "and TTS have finished."
                )
                write_marker(
                    marker_path,
                    base,
                    "ASSISTANT_RESPONSE_COMPLETE_OPERATOR",
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                    detail=(
                        "coarse TTS-complete marker; ASR/LLM timing must be "
                        "derived from decrypted network events"
                    ),
                )

                capture_screenshot(
                    base,
                    run_dir / "response.png",
                )
                capture_ui_xml(
                    base,
                    run_dir / "response.xml",
                )

                asr_operator_match = ask_yes_no(
                    "Does the displayed/observable recognized request include "
                    "all critical words, numbers, and output constraints from "
                    "the exact prompt?",
                    default=False,
                )

                write_marker(
                    marker_path,
                    base,
                    (
                        "ATTEMPT_OPERATOR_ACCEPTED_ASR"
                        if asr_operator_match
                        else "ATTEMPT_REJECTED_ASR"
                    ),
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                )

                (run_dir / "operator-observation.json").write_text(
                    json.dumps(
                        {
                            "model": model,
                            "prompt_id": prompt_id,
                            "repetition": repetition,
                            "attempt": attempt,
                            "input_mode": "wearer_manual_voice",
                            "wake_phrase": args.wake_phrase,
                            "intended_prompt": prompt_entry["text"],
                            "timing_source": {
                                "wake_arm": "WAKE_AND_QUESTION_ARMED",
                                "question_end": "decrypted_final_recognized_speech",
                                "llm_response": "decrypted_llm_events",
                                "tts_complete": (
                                    "ASSISTANT_RESPONSE_COMPLETE_OPERATOR"
                                ),
                            },
                            "operator_asr_match": asr_operator_match,
                            "qualification_status": (
                                "PENDING_PACKET_VALIDATION"
                                if asr_operator_match
                                else "REJECTED_OPERATOR_ASR_MISMATCH"
                            ),
                            "recorded_utc": utc_now(),
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

                prompt_enter(
                    "In PCAPdroid, stop capture and export the raw PCAP plus "
                    "SSL key log/archive to Download/PCAPdroid. Export even "
                    "when this attempt was rejected."
                )
                write_marker(
                    marker_path,
                    base,
                    "PCAP_CAPTURE_STOPPED_AND_EXPORTED",
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                )

                pulled = pull_new_exports(
                    base,
                    user_id,
                    collection_uri,
                    baseline_ids,
                    capture_start_epoch,
                    run_dir / "pcapdroid-export",
                    run_label,
                )

                if not pulled:
                    print(
                        "\nNo new MediaStore export was detected. "
                        "The evidence has not been discarded."
                    )
                    prompt_enter(
                        "Verify the PCAPdroid export completed into "
                        "Download/PCAPdroid. The script will rescan."
                    )
                    pulled = pull_new_exports(
                        base,
                        user_id,
                        collection_uri,
                        baseline_ids,
                        capture_start_epoch,
                        run_dir / "pcapdroid-export",
                        run_label,
                    )

                pcap_count = sum(
                    is_pcap_name(Path(str(item["destination"])).name)
                    for item in pulled
                )
                ssl_keylog_count = sum(
                    is_ssl_keylog_name(Path(str(item["destination"])).name)
                    for item in pulled
                )

                (run_dir / "pulled-media-private.json").write_text(
                    json.dumps(pulled, indent=2) + "\n",
                    encoding="utf-8",
                )

                cumulative_pcaps = (
                    sum(
                        int(item.get("pcap_count", 0))
                        for item in results
                    )
                    + pcap_count
                )
                cumulative_keylogs = (
                    sum(
                        int(item.get("ssl_keylog_count", 0))
                        for item in results
                    )
                    + ssl_keylog_count
                )

                print(
                    f"Current attempt: pulled {pcap_count} PCAP file(s), "
                    f"{ssl_keylog_count} SSL key-log file(s)."
                )
                print(
                    f"Cumulative test attempts: {cumulative_pcaps} PCAP(s), "
                    f"{cumulative_keylogs} SSL key log(s)."
                )

                if pcap_count == 0:
                    print(
                        "WARNING: no new PCAP/PCAPNG/CAP was pulled for "
                        "this attempt.",
                        file=sys.stderr,
                    )
                if ssl_keylog_count == 0:
                    print(
                        "WARNING: no SSL key log was pulled. Ensure "
                        "`sslkeylogfile.txt` was exported before continuing.",
                        file=sys.stderr,
                    )
            finally:
                stop_logcat(logcat_process)

            attempt_accepted = (
                asr_operator_match
                and pcap_count > 0
                and ssl_keylog_count > 0
            )
            if attempt_accepted:
                qualification_status = (
                    "OPERATOR_ACCEPTED_PENDING_PACKET_VALIDATION"
                )
            elif not asr_operator_match:
                qualification_status = "REJECTED_OPERATOR_ASR_MISMATCH"
            elif pcap_count == 0 and ssl_keylog_count == 0:
                qualification_status = "REJECTED_NO_PCAP_OR_SSL_KEYLOG"
            elif pcap_count == 0:
                qualification_status = "REJECTED_NO_PCAP"
            else:
                qualification_status = "REJECTED_NO_SSL_KEYLOG"

            results.append(
                {
                    "sequence": index,
                    "model": model,
                    "prompt_id": prompt_id,
                    "repetition": repetition,
                    "attempt": attempt,
                    "input_mode": "wearer_manual_voice",
                    "wake_phrase": args.wake_phrase,
                    "run_directory": str(run_dir),
                    "operator_asr_match": asr_operator_match,
                    "pcap_count": pcap_count,
                    "ssl_keylog_count": ssl_keylog_count,
                    "qualification_status": qualification_status,
                    "pulled_media": pulled,
                }
            )

            write_marker(
                marker_path,
                base,
                "ATTEMPT_COMPLETE",
                model=model,
                prompt_id=prompt_id,
                repetition=repetition,
                attempt=attempt,
                detail=qualification_status,
            )

            if attempt_accepted:
                slot_accepted = True
                accepted_slots += 1
                write_marker(
                    marker_path,
                    base,
                    "QUALIFICATION_SLOT_ACCEPTED",
                    model=model,
                    prompt_id=prompt_id,
                    repetition=repetition,
                    attempt=attempt,
                )
                break

            if attempt < args.max_attempts:
                print(
                    "\nThis attempt does not count as the qualified trial. "
                    "The same slot will be repeated with a fresh session and "
                    "new PCAP."
                )

        if not slot_accepted:
            failure = {
                "sequence": index,
                "model": model,
                "prompt_id": prompt_id,
                "repetition": repetition,
                "attempts_exhausted": args.max_attempts,
            }
            failed_slots.append(failure)
            write_marker(
                marker_path,
                base,
                "QUALIFICATION_SLOT_FAILED",
                model=model,
                prompt_id=prompt_id,
                repetition=repetition,
                attempt=args.max_attempts,
                detail="maximum attempts exhausted",
            )
            print(
                "\nWARNING: qualification slot failed after all attempts. "
                "The script will continue so the remaining evidence is kept.",
                file=sys.stderr,
            )

    run_info["accepted_slots_operator_precheck"] = accepted_slots
    run_info["required_accepted_slots"] = len(schedule)
    run_info["failed_slots"] = failed_slots

    aggregate_attempt_pcap_count = sum(
        int(item.get("pcap_count", 0))
        for item in results
    )
    accepted_attempt_pcap_count = sum(
        int(item.get("pcap_count", 0))
        for item in results
        if item.get("qualification_status")
        == "OPERATOR_ACCEPTED_PENDING_PACKET_VALIDATION"
    )
    aggregate_attempt_keylog_count = sum(
        int(item.get("ssl_keylog_count", 0))
        for item in results
    )
    accepted_attempt_keylog_count = sum(
        int(item.get("ssl_keylog_count", 0))
        for item in results
        if item.get("qualification_status")
        == "OPERATOR_ACCEPTED_PENDING_PACKET_VALIDATION"
    )

    evidence_tree_pcaps = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and is_pcap_name(path.name)
    )
    evidence_tree_keylogs = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and is_ssl_keylog_name(path.name)
    )

    run_info["evidence_summary"] = {
        "aggregate_attempt_pcap_count": aggregate_attempt_pcap_count,
        "accepted_attempt_pcap_count": accepted_attempt_pcap_count,
        "evidence_tree_pcap_count": len(evidence_tree_pcaps),
        "evidence_tree_pcaps": [
            str(path.relative_to(root))
            for path in evidence_tree_pcaps
        ],
        "aggregate_attempt_ssl_keylog_count": (
            aggregate_attempt_keylog_count
        ),
        "accepted_attempt_ssl_keylog_count": (
            accepted_attempt_keylog_count
        ),
        "evidence_tree_ssl_keylog_count": len(evidence_tree_keylogs),
        "evidence_tree_ssl_keylogs": [
            str(path.relative_to(root))
            for path in evidence_tree_keylogs
        ],
        "required_accepted_pcap_minimum": len(schedule),
        "required_accepted_ssl_keylog_minimum": len(schedule),
    }

    write_marker(
        marker_path,
        base,
        "TEST_COMPLETE",
        detail=json.dumps(
            run_info["evidence_summary"],
            separators=(",", ":"),
        ),
    )
    run_info["end_utc"] = utc_now()
    run_info["results"] = results

    print("\nAggregate decryption-evidence validation")
    print("----------------------------------------")
    print(f"Required accepted slots:         {len(schedule)}")
    print(f"Operator-accepted slots:         {accepted_slots}")
    print(f"PCAPs from all attempts:         {aggregate_attempt_pcap_count}")
    print(f"PCAPs from accepted attempts:    {accepted_attempt_pcap_count}")
    print(f"PCAP files in evidence tree:     {len(evidence_tree_pcaps)}")
    print(f"Key logs from all attempts:      {aggregate_attempt_keylog_count}")
    print(f"Key logs from accepted attempts: {accepted_attempt_keylog_count}")
    print(f"Key logs in evidence tree:       {len(evidence_tree_keylogs)}")

    aggregate_gate_pass = (
        accepted_slots == len(schedule)
        and accepted_attempt_pcap_count >= len(schedule)
        and len(evidence_tree_pcaps) >= len(schedule)
        and accepted_attempt_keylog_count >= len(schedule)
        and len(evidence_tree_keylogs) >= len(schedule)
    )
    run_info["evidence_summary"]["aggregate_gate_pass"] = (
        aggregate_gate_pass
    )

    (root / "run-info-private.json").write_text(
        json.dumps(run_info, indent=2) + "\n",
        encoding="utf-8",
    )

    if not aggregate_gate_pass:
        print(
            "WARNING: aggregate decryption-evidence gate FAILED. "
            "The evidence directory is preserved, but the test is not "
            "complete until every accepted slot has a PCAP and SSL key log.",
            file=sys.stderr,
        )
    else:
        print("Aggregate decryption-evidence gate: PASS")

    sums = write_sha256sums(root)
    print(f"\nSHA-256 manifest: {sums}")

    private_zip: Optional[Path] = None
    if args.zip:
        private_zip = make_private_zip(root)
        print(f"Private evidence ZIP: {private_zip}")
        print(f"ZIP SHA-256: {sha256_file(private_zip)}")

    print(
        "\nTest 14A-r2 manual-voice capture finished. "
        + (
            "Aggregate PCAP gate passed."
            if aggregate_gate_pass
            else "Aggregate PCAP gate failed; use the audit/recovery tool."
        )
    )
    print(f"Evidence directory: {root}")
    print(
        "Upload the private evidence ZIP or the run-info JSON, event markers, "
        "PCAP files, SSL key logs, and focused logs for evaluation. "
        "Operator acceptance remains subject to decrypted ASR validation."
    )
    return 0 if aggregate_gate_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestAbort as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("\nERROR: interrupted by user.", file=sys.stderr)
        raise SystemExit(130)
