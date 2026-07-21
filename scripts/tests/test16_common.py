#!/usr/bin/env python3
"""Shared privacy-first helpers for Rokid Test 16.

Private raw evidence stays on the operator's Mac. Only sanitized summaries are
placed in the upload ZIP.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qsl
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

HI_ROKID = "com.rokid.sprite.global.aiapp"
PCAPDROID = "com.emanuelef.remote_capture"
EXPECTED_APKS_SHA256 = "df99ba51906e1c7866135d7cd1400fca62eae4205eed78c1c8730da3d33cdc3a"

PCAP_SUFFIXES = (".pcap", ".pcapng", ".cap")
SSL_TOKENS = ("sslkeylog", "ssl-keylog", "ssl_keylog", "keylog", "tlskey")
SIDECAR_SUFFIXES = (".csv", ".json", ".zip", ".txt", ".log")
MEDIA_PROJECTION = "_id:_display_name:relative_path:date_modified:date_added:_size:mime_type"

SAFE_PAYMENT_KEYS = {
    "DEFAULT_PAYMENT",
    "WX_PAYMENT",
    "ALI_PAYMENT",
    "ALI_CAR_PARKING",
    "ALI_CITY_SIGHTSEEING",
    "ALI_BICYCLE_SERVICE",
}
SAFE_ROUTE_KEYS = {"base_model_no", "vl_model_no", "is_global"}
SAFE_EVENT_VALUES = {
    "init_scene",
    "processing_audio",
    "recognized_speech",
    "take_photo",
    "processing_image",
    "synthesized_speech",
    "llm",
    "update_param",
    "ping",
    "pong",
}

CATEGORY_PATTERNS: Dict[str, re.Pattern[str]] = {
    "account_identity": re.compile(
        r"(account|user_?id|email|birthday|date_?of_?birth|profile)", re.I
    ),
    "authentication_session": re.compile(
        r"(authorization|access_?token|refresh_?token|cookie|session|jwt|bearer)", re.I
    ),
    "device_identifier": re.compile(
        r"(serial|android_?id|advertising_?id|imei|imsi|device_?id|device_?no|mac_?address|glasses_?id)", re.I
    ),
    "location_address": re.compile(
        r"(latitude|longitude|\blat\b|\blon\b|\blng\b|gps|location|address|street|city|region|postal)", re.I
    ),
    "payment_configuration": re.compile(
        r"(payment_binding|default_payment|ali_payment|wx_payment|alipay|wechat_payment)", re.I
    ),
    "installed_application_list": re.compile(
        r"(installed_?apps?|app_?list|package_?list|query_all_packages)", re.I
    ),
    "contacts_phonebook": re.compile(
        r"(contacts?|address_?book|phone_?number|caller)", re.I
    ),
    "calendar_schedule": re.compile(
        r"(calendar|schedule|event_?list|reminder)", re.I
    ),
    "audio_voice_prompt": re.compile(
        r"(processing_audio|recognized_speech|audio_(?:url|data|bytes|content)|"
        r"voice_(?:recording|content|data)|microphone|speech_(?:text|audio)|user_prompt)",
        re.I,
    ),
    "image_visual": re.compile(
        r"(processing_image|take_photo|image_(?:url|data|bytes|content)|"
        r"photo_(?:url|data|bytes)|camera_(?:capture|frame)|webp|oss_(?:url|object|key))",
        re.I,
    ),
    "weather_context": re.compile(
        r"(weather|temperature|forecast)", re.I
    ),
    "device_state": re.compile(
        r"(battery|brightness|volume|firmware|device_type)", re.I
    ),
}

LOG_EVENT_PATTERNS: Dict[str, re.Pattern[str]] = {
    "hi_rokid_process_started": re.compile(
        r"(Start proc|START u\d+).*(com\.rokid\.sprite\.global\.aiapp)", re.I
    ),
    "hi_rokid_force_stopped": re.compile(
        r"Force stopping com\.rokid\.sprite\.global\.aiapp", re.I
    ),
    "hi_rokid_process_killed": re.compile(
        r"(Killing|Process.*died|ProcessRecord.*removed).*(com\.rokid\.sprite\.global\.aiapp)", re.I
    ),
    "ai_service_started": re.compile(
        r"(AiService).*(start|foreground|created|onCreate)", re.I
    ),
    "ai_service_stopped": re.compile(
        r"(AiService).*(stop|destroy|removed)", re.I
    ),
    "location_service_started": re.compile(
        r"(LocationService).*(start|foreground|created|onCreate)", re.I
    ),
    "location_service_stopped": re.compile(
        r"(LocationService).*(stop|destroy|removed)", re.I
    ),
    "bluetooth_connected": re.compile(
        r"(RFCOMM|BluetoothController|socket).*(connected|connect success)", re.I
    ),
    "bluetooth_disconnected": re.compile(
        r"(RFCOMM|BluetoothController|socket).*(disconnect|closed|lost)", re.I
    ),
    "ai_websocket_open": re.compile(
        r"(ai-cloud-global\.rokid\.com|/ws/ai).*(open|connected|101)", re.I
    ),
    "ai_websocket_close": re.compile(
        r"(ai-cloud-global\.rokid\.com|/ws/ai).*(close|disconnect|failure)", re.I
    ),
    "pcapdroid_capture_started": re.compile(
        r"(CaptureService|PCAPdroid).*(start|VPN created|packet loop)", re.I
    ),
    "pcapdroid_empty_capture": re.compile(
        r"(Host LRU cache size:\s*0|deletePcapFile)", re.I
    ),
    "android_restore_activity": re.compile(
        r"(BackupManager|restoreAtInstall|restore.*package|auto.?restore)", re.I
    ),
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
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        check=check,
        text=text,
        stdout=stdout,
        stderr=stderr,
        timeout=timeout,
    )


def find_adb() -> str:
    candidates = [
        os.environ.get("ADB", ""),
        str(Path.home() / "Library/Android/sdk/platform-tools/adb"),
        shutil.which("adb") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise TestAbort("adb was not found.")


def find_tshark() -> Optional[str]:
    candidates = [
        os.environ.get("TSHARK", ""),
        shutil.which("tshark") or "",
        "/Applications/Wireshark.app/Contents/MacOS/tshark",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def adb_base(serial: str) -> List[str]:
    return [find_adb(), "-s", serial]


def adb_shell(base: Sequence[str], *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run([*base, "shell", *args], check=check)


def discover_pixel_serial() -> str:
    adb = find_adb()
    run([adb, "start-server"], check=False)
    result = run([adb, "devices", "-l"], check=False)
    candidates = []
    all_devices = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or parts[1] != "device":
            continue
        serial = parts[0]
        all_devices.append(serial)
        lower = line.lower()
        if "model:pixel_7" in lower or "product:panther" in lower:
            candidates.append(serial)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise TestAbort("Multiple Pixel 7 devices detected; use --serial.")
    if len(all_devices) == 1:
        return all_devices[0]
    if not all_devices:
        raise TestAbort("No authorized Android device is connected.")
    raise TestAbort("Multiple Android devices connected; use --serial.")


def validate_pixel(base: Sequence[str]) -> Dict[str, str]:
    state = run([*base, "get-state"], check=False)
    if state.returncode != 0 or state.stdout.strip() != "device":
        raise TestAbort("Selected Pixel is not in adb state=device.")

    def prop(name: str) -> str:
        return adb_shell(base, "getprop", name, check=False).stdout.strip()

    model = prop("ro.product.model")
    device = prop("ro.product.device")
    if model != "Pixel 7" and device != "panther":
        raise TestAbort(f"Expected Pixel 7/panther; detected model={model}, device={device}.")

    serial = run([*base, "get-serialno"], check=False).stdout.strip()
    user = adb_shell(base, "am", "get-current-user", check=False).stdout.strip() or "0"
    return {
        "serial": serial,
        "model": model,
        "device": device,
        "manufacturer": prop("ro.product.manufacturer"),
        "android_release": prop("ro.build.version.release"),
        "sdk": prop("ro.build.version.sdk"),
        "build_fingerprint": prop("ro.build.fingerprint"),
        "current_user": user,
    }


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def prompt_enter(message: str) -> None:
    try:
        input(f"\n{message}\nPress Enter to continue... ")
    except (EOFError, KeyboardInterrupt) as exc:
        raise TestAbort("Operator aborted.") from exc


def ask_yes_no(message: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        value = input(f"{message} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt) as exc:
        raise TestAbort("Operator aborted.") from exc
    if not value:
        return default
    return value in {"y", "yes"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_privacy_key() -> Tuple[bytes, Path]:
    key_path = Path.home() / "rokid-nettest" / "private" / "test16-redaction-key.bin"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        key_path.write_bytes(secrets.token_bytes(32))
        key_path.chmod(0o600)
    key = key_path.read_bytes()
    if len(key) < 32:
        raise TestAbort(f"Privacy key is invalid: {key_path}")
    return key, key_path


def pseudonym(key: bytes, namespace: str, value: str, length: int = 16) -> str:
    digest = hmac.new(key, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()
    return f"{namespace}_{digest[:length]}"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_pm_packages(text: str) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    # Typical:
    # package:/data/app/.../base.apk=com.foo installer=com.android.vending uid:10123
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        payload = line[len("package:"):]
        match = re.match(
            r"(?P<path>.*?)=(?P<pkg>[A-Za-z0-9_.]+)"
            r"(?:\s+installer=(?P<installer>\S+))?"
            r"(?:\s+uid:(?P<uid>\d+))?",
            payload,
        )
        if not match:
            continue
        item = match.groupdict()
        pkg = item["pkg"]
        result[pkg] = {
            "package": pkg,
            "path": item.get("path") or "",
            "installer": item.get("installer") or "",
            "uid": item.get("uid") or "",
        }
    return result


def collect_package_inventory(base: Sequence[str], destination: Path) -> Dict[str, Dict[str, str]]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = adb_shell(
        base,
        "pm",
        "list",
        "packages",
        "-f",
        "-U",
        "-i",
        "-u",
        check=False,
    )
    destination.write_text(result.stdout + result.stderr, encoding="utf-8")
    return parse_pm_packages(result.stdout)


def package_details(base: Sequence[str], package: str, destination: Optional[Path] = None) -> Dict[str, Any]:
    result = adb_shell(base, "dumpsys", "package", package, check=False)
    body = result.stdout
    if destination:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(body + result.stderr, encoding="utf-8")

    def first(pattern: str) -> str:
        match = re.search(pattern, body)
        return match.group(1).strip() if match else ""

    paths_result = adb_shell(base, "pm", "path", package, check=False)
    paths = [
        line.split("package:", 1)[1].strip()
        for line in paths_result.stdout.splitlines()
        if line.startswith("package:")
    ]
    return {
        "package": package,
        "version_name": first(r"\bversionName=([^\s]+)"),
        "version_code": first(r"\bversionCode=(\d+)"),
        "uid": first(r"\buserId=(\d+)"),
        "first_install_time": first(r"\bfirstInstallTime=(.+)"),
        "last_update_time": first(r"\blastUpdateTime=(.+)"),
        "installer": first(r"\binstallerPackageName=([^\s]+)"),
        "paths": paths,
    }


def hash_remote_file(base: Sequence[str], remote_path: str) -> Dict[str, Any]:
    process = subprocess.Popen(
        [*base, "exec-out", "cat", remote_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    digest = hashlib.sha256()
    size = 0
    assert process.stdout is not None
    for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
        digest.update(chunk)
        size += len(chunk)
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    returncode = process.wait()
    return {
        "basename": Path(remote_path).name,
        "size": size,
        "sha256": digest.hexdigest() if returncode == 0 else "",
        "read_ok": returncode == 0,
        "error_present": bool(stderr.strip()),
    }


def sanitized_package_diff(
    key: bytes,
    before: Dict[str, Dict[str, str]],
    after: Dict[str, Dict[str, str]],
    known_clear: Set[str],
) -> Dict[str, Any]:
    before_names = set(before)
    after_names = set(after)
    added = sorted(after_names - before_names)
    removed = sorted(before_names - after_names)

    def item(pkg: str, source: Dict[str, Dict[str, str]], clear: bool) -> Dict[str, Any]:
        data = source[pkg]
        return {
            "package": pkg if clear else "",
            "package_hmac": pseudonym(key, "pkg", pkg),
            "uid_hmac": pseudonym(key, "uid", data.get("uid", "")) if data.get("uid") else "",
            "installer": (
                data.get("installer", "")
                if clear and data.get("installer", "") in {"com.android.vending", "com.google.android.packageinstaller", "com.android.shell"}
                else ""
            ),
        }

    return {
        "before_count": len(before),
        "after_count": len(after),
        "added_count": len(added),
        "removed_count": len(removed),
        "added": [item(pkg, after, True) for pkg in added],
        "removed": [item(pkg, before, pkg in known_clear) for pkg in removed],
        "before_package_hmacs": sorted(pseudonym(key, "pkg", pkg) for pkg in before_names),
        "after_package_hmacs": sorted(pseudonym(key, "pkg", pkg) for pkg in after_names),
    }


def start_logcat(base: Sequence[str], destination: Path) -> subprocess.Popen:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = destination.open("wb")
    process = subprocess.Popen(
        [*base, "logcat", "-b", "all", "-v", "threadtime"],
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
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


def sanitize_logcat(private_log: Path) -> Dict[str, Any]:
    counts = Counter()
    first_seen: Dict[str, str] = {}
    last_seen: Dict[str, str] = {}
    if not private_log.exists():
        return {"available": False, "events": {}}

    with private_log.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            timestamp = line[:18].strip()
            for name, pattern in LOG_EVENT_PATTERNS.items():
                if pattern.search(line):
                    counts[name] += 1
                    first_seen.setdefault(name, timestamp)
                    last_seen[name] = timestamp

    events = {
        name: {
            "count": count,
            "first_seen_local_log_time": first_seen.get(name, ""),
            "last_seen_local_log_time": last_seen.get(name, ""),
        }
        for name, count in sorted(counts.items())
    }
    return {"available": True, "events": events}


def collect_target_runtime_state(
    base: Sequence[str],
    destination: Path,
    package_names: Sequence[str],
    suffix: str,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    package_pattern = "|".join(re.escape(pkg) for pkg in package_names if pkg)
    package_pattern = package_pattern or re.escape(HI_ROKID)
    commands = {
        f"ps-target-{suffix}.txt": [
            *base, "shell", "sh", "-c",
            f"ps -A -o USER,PID,PPID,NAME,ARGS 2>&1 | grep -E '{package_pattern}' || true",
        ],
        f"services-target-{suffix}.txt": [
            *base, "shell", "sh", "-c",
            f"dumpsys activity services 2>&1 | grep -E -B 5 -A 15 '{package_pattern}' || true",
        ],
        f"jobs-target-{suffix}.txt": [
            *base, "shell", "sh", "-c",
            f"dumpsys jobscheduler 2>&1 | grep -E -B 4 -A 12 '{package_pattern}' || true",
        ],
        f"alarms-target-{suffix}.txt": [
            *base, "shell", "sh", "-c",
            f"dumpsys alarm 2>&1 | grep -E -B 3 -A 8 '{package_pattern}' || true",
        ],
        f"notifications-target-{suffix}.txt": [
            *base, "shell", "sh", "-c",
            f"dumpsys notification 2>&1 | grep -E -B 4 -A 10 '{package_pattern}|AI Service' || true",
        ],
        f"companion-target-{suffix}.txt": [
            *base, "shell", "sh", "-c",
            f"dumpsys companiondevice 2>&1 | grep -E -B 4 -A 12 '{package_pattern}' || true",
        ],
        f"power-{suffix}.txt": [*base, "shell", "dumpsys", "power"],
        f"deviceidle-{suffix}.txt": [*base, "shell", "dumpsys", "deviceidle"],
    }
    for name, command in commands.items():
        result = run(command, check=False)
        (destination / name).write_text(result.stdout + result.stderr, encoding="utf-8")


def sanitize_runtime_state(private_dir: Path, package_names: Sequence[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "files_scanned": 0,
        "package_presence": {},
        "components": [],
        "sample_counts": {
            "process_present": 0,
            "active_service_present": 0,
            "ai_service_present": 0,
            "location_service_present": 0,
            "foreground_notification_present": 0,
            "companion_association_present": 0,
        },
    }
    component_counter = Counter()
    package_pattern = re.compile("|".join(re.escape(pkg) for pkg in package_names if pkg) or re.escape(HI_ROKID))
    for path in private_dir.rglob("*.txt"):
        result["files_scanned"] += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        lower_name = path.name.lower()
        package_seen = bool(package_pattern.search(text))
        for package in package_names:
            result["package_presence"].setdefault(package, 0)
            if package in text:
                result["package_presence"][package] += 1
        if package_seen and lower_name.startswith("ps-target-"):
            result["sample_counts"]["process_present"] += 1
        if package_seen and lower_name.startswith("services-target-"):
            result["sample_counts"]["active_service_present"] += 1
        if "AiService" in text and lower_name.startswith("services-target-"):
            result["sample_counts"]["ai_service_present"] += 1
        if "LocationService" in text and lower_name.startswith("services-target-"):
            result["sample_counts"]["location_service_present"] += 1
        if lower_name.startswith("notifications-target-") and (
            "ai_service_channel" in text or "Rokid AI service is running" in text or "AI Service" in text
        ):
            result["sample_counts"]["foreground_notification_present"] += 1
        if package_seen and lower_name.startswith("companion-target-"):
            result["sample_counts"]["companion_association_present"] += 1
        for match in re.findall(
            r"(?:com\.rokid\.[A-Za-z0-9_.$]+(?:Service|Receiver|Provider)|"
            r"com\.google\.[A-Za-z0-9_.$]+(?:Service|Receiver|Provider))",
            text,
        ):
            if len(match) < 200:
                component_counter[match] += 1
    result["components"] = [
        {"component": name, "mentions": count}
        for name, count in component_counter.most_common(100)
    ]
    return result


SENSITIVE_ANDROID_PERMISSIONS = (
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.READ_CONTACTS",
    "android.permission.READ_CALENDAR",
    "android.permission.WRITE_CALENDAR",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.NEARBY_WIFI_DEVICES",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_AUDIO",
)


def collect_sanitized_permission_state(
    base: Sequence[str],
    package: str,
    private_destination: Optional[Path] = None,
) -> Dict[str, Any]:
    result = adb_shell(base, "dumpsys", "package", package, check=False)
    text = result.stdout + result.stderr
    if private_destination:
        private_destination.parent.mkdir(parents=True, exist_ok=True)
        private_destination.write_text(text, encoding="utf-8")

    permissions: Dict[str, str] = {}
    for permission in SENSITIVE_ANDROID_PERMISSIONS:
        match = re.search(
            rf"{re.escape(permission)}:\\s+granted=(true|false)", text, re.I
        )
        if match:
            permissions[permission] = "granted" if match.group(1).lower() == "true" else "denied"
        elif re.search(rf"^\\s*{re.escape(permission)}$", text, re.M):
            permissions[permission] = "granted_or_declared"
        else:
            permissions[permission] = "not_observed"

    listeners = adb_shell(
        base, "settings", "get", "secure", "enabled_notification_listeners", check=False
    ).stdout
    return {
        "permissions": permissions,
        "notification_listener_enabled": package in listeners,
    }


def parse_content_rows(text: str) -> List[Dict[str, str]]:
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("Row:"):
            continue
        payload = re.sub(r"^Row:\s*\d+\s*", "", line, count=1)
        parts = re.split(r",\s+(?=[A-Za-z_][A-Za-z0-9_]*=)", payload)
        row: Dict[str, str] = {}
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                row[key.strip()] = value.strip()
        if row.get("_id"):
            rows.append(row)
    return rows


def query_media_store(base: Sequence[str], user_id: str) -> Tuple[str, List[Dict[str, str]]]:
    failures = []
    for volume in ("external_primary", "external"):
        uri = f"content://media/{volume}/file"
        result = adb_shell(
            base, "content", "query", "--user", user_id,
            "--uri", uri, "--projection", MEDIA_PROJECTION, check=False
        )
        combined = result.stdout + "\n" + result.stderr
        if result.returncode == 0 and "Exception" not in combined:
            return uri, parse_content_rows(result.stdout)
        failures.append(combined)
    raise TestAbort("MediaStore query failed.")


def media_ids(rows: Iterable[Dict[str, str]]) -> Set[str]:
    return {row["_id"] for row in rows if row.get("_id")}


def classify_export(name: str) -> str:
    lowered = re.sub(r"\s*\(\d+\)$", "", name.lower())
    if lowered.endswith(PCAP_SUFFIXES):
        return "pcap"
    if any(token in lowered for token in SSL_TOKENS):
        return "ssl_keylog"
    if lowered.endswith(SIDECAR_SUFFIXES):
        return "sidecar"
    return "other"


def relevant_new_exports(
    rows: Iterable[Dict[str, str]],
    baseline_ids: Set[str],
    phase_start_epoch: int,
) -> List[Dict[str, str]]:
    selected = []
    for row in rows:
        if not row.get("_id") or row["_id"] in baseline_ids:
            continue
        kind = classify_export(row.get("_display_name", ""))
        if kind == "other":
            continue
        rel = row.get("relative_path", "").lower()
        name = row.get("_display_name", "").lower()
        if kind == "sidecar" and "pcapdroid" not in rel and "pcapdroid" not in name:
            continue
        changed = max(int(row.get("date_modified", "0") or 0), int(row.get("date_added", "0") or 0))
        if changed and changed < phase_start_epoch - 120:
            continue
        selected.append(row)
    return sorted(selected, key=lambda item: int(item.get("_id", "0") or 0))


def pull_media_uri(
    base: Sequence[str],
    user_id: str,
    uri: str,
    destination: Path,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        process = subprocess.run(
            [*base, "exec-out", "content", "read", "--user", user_id, "--uri", uri],
            stdout=output,
            stderr=subprocess.PIPE,
            check=False,
        )
    if process.returncode != 0:
        destination.unlink(missing_ok=True)
        raise TestAbort(f"Could not pull MediaStore item {uri}.")


def pull_phase_exports(
    base: Sequence[str],
    user_id: str,
    collection_uri: str,
    baseline_ids: Set[str],
    phase_start_epoch: int,
    destination: Path,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, str]] = []
    for _ in range(8):
        collection_uri, rows = query_media_store(base, user_id)
        selected = relevant_new_exports(rows, baseline_ids, phase_start_epoch)
        if any(classify_export(row.get("_display_name", "")) == "pcap" for row in selected):
            break
        time.sleep(2)

    pulled = []
    for row in selected:
        media_id = row["_id"]
        original = row.get("_display_name", f"media-{media_id}")
        kind = classify_export(original)
        safe_name = re.sub(r"[^A-Za-z0-9._()-]+", "_", original)
        local = destination / f"{kind}--media-{media_id}--{safe_name}"
        pull_media_uri(base, user_id, f"{collection_uri}/{media_id}", local)
        pulled.append({
            "kind": kind,
            "original_name": original,
            "path": str(local),
            "size": local.stat().st_size,
            "sha256": sha256_file(local),
        })
    return pulled


def summarize_connections_csv(
    csv_paths: Sequence[Path],
    key: bytes,
    target_packages: Set[str],
    target_uids: Set[str],
) -> Dict[str, Any]:
    rows_out: Dict[Tuple[str, str, str, str, str], Dict[str, Any]] = {}
    total_rows = 0
    included_rows = 0

    for path in csv_paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                total_rows += 1
                package = (row.get("PackageName") or "").strip()
                uid = (row.get("UID") or "").strip()
                if package not in target_packages and uid not in target_uids:
                    continue
                included_rows += 1
                host = (row.get("Info") or "").strip().lower().rstrip(".")
                proto = (row.get("Proto") or "").strip()
                status = (row.get("Status") or "").strip()
                port = (row.get("DstPort") or "").strip()
                package_label = package if package in target_packages else ""
                package_hmac = pseudonym(key, "pkg", package or f"uid:{uid}")
                identity = package_label or package_hmac
                k = (identity, host, proto, status, port)
                item = rows_out.setdefault(k, {
                    "package": package_label,
                    "package_hmac": package_hmac,
                    "hostname": host,
                    "protocol": proto,
                    "status": status,
                    "destination_port": port,
                    "connections": 0,
                    "bytes_sent": 0,
                    "bytes_received": 0,
                    "packets_sent": 0,
                    "packets_received": 0,
                })
                item["connections"] += 1
                for source, target in [
                    ("BytesSent", "bytes_sent"),
                    ("BytesRcvd", "bytes_received"),
                    ("PktsSent", "packets_sent"),
                    ("PktsRcvd", "packets_received"),
                ]:
                    try:
                        item[target] += int(row.get(source) or 0)
                    except ValueError:
                        pass

    endpoints = sorted(
        rows_out.values(),
        key=lambda item: (item["package"] or item["package_hmac"], item["hostname"], item["protocol"]),
    )
    return {
        "source_rows_total": total_rows,
        "target_rows_included": included_rows,
        "endpoints": endpoints,
        "target_hostnames": sorted({item["hostname"] for item in endpoints if item["hostname"]}),
    }


def tshark_run(tshark: str, args: Sequence[str]) -> Iterator[str]:
    process = subprocess.Popen(
        [tshark, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        yield line.rstrip("\n")
    process.wait()


def decode_possible_hex(value: str) -> bytes:
    compact = re.sub(r"[:\s]", "", value)
    if compact and len(compact) % 2 == 0 and re.fullmatch(r"[0-9A-Fa-f]+", compact):
        try:
            return bytes.fromhex(compact)
        except ValueError:
            pass
    return value.encode("utf-8", errors="replace")


def iter_json_objects(value: Any) -> Iterator[Any]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_json_objects(child)



DIRECTION_PHONE_TO_SERVER = "PHONE_TO_SERVER"
DIRECTION_SERVER_TO_PHONE = "SERVER_TO_PHONE"
DIRECTION_UNKNOWN = "UNKNOWN"

SENSITIVE_VALUE_KEY_ALIASES = {
    "email": "email",
    "password": "password",
    "passwordhash": "password_hash",
    "rokidtoken": "rokid_token",
    "authtoken": "auth_token",
    "refreshtoken": "refresh_token",
    "idtoken": "id_token",
    "accesstoken": "access_token",
    "logintoken": "login_token",
    "authorization": "authorization",
    "cookie": "cookie",
    "sessionid": "session_id",
    "localid": "account_local_id",
    "userid": "user_id",
    "accountid": "account_id",
    "androidid": "android_id",
    "advertisingid": "advertising_id",
    "deviceid": "device_id",
    "deviceno": "device_number",
    "serialnumber": "serial_number",
    "glassesid": "glasses_id",
    "latitude": "latitude",
    "longitude": "longitude",
    "lat": "latitude",
    "lon": "longitude",
    "lng": "longitude",
    "address": "address",
    "homeaddress": "home_address",
    "workaddress": "work_address",
    "installedapps": "installed_apps",
    "applist": "app_list",
    "packagelist": "package_list",
}


def _new_payload_bucket() -> Dict[str, Any]:
    return {
        "json_keys": Counter(),
        "event_types": Counter(),
        "sensitive_category_presence": Counter(),
        "sensitive_value_states": defaultdict(Counter),
        "safe_values": defaultdict(Counter),
        "payment_binding_safe": defaultdict(Counter),
    }


def _safe_schema_key(value: Any) -> str:
    key = str(value).strip()
    if not key or len(key) > 96:
        return "{dynamic_key}"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]*", key):
        return "{dynamic_key}"
    if re.search(r"[0-9a-fA-F]{24,}", key):
        return "{dynamic_key}"
    return key


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _value_state(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean_true" if value else "boolean_false"
    if isinstance(value, (int, float)):
        return "numeric_zero" if value == 0 else "numeric_nonzero"
    if isinstance(value, str):
        return "empty" if value == "" else "nonempty"
    if isinstance(value, list):
        return "list_empty" if not value else "list_nonempty"
    if isinstance(value, dict):
        return "object_empty" if not value else "object_nonempty"
    return "other"


def _record_key_value(bucket: Dict[str, Any], key_name: Any, value: Any) -> None:
    safe_key = _safe_schema_key(key_name)
    bucket["json_keys"][safe_key] += 1
    for category, pattern in CATEGORY_PATTERNS.items():
        if pattern.search(str(key_name)):
            bucket["sensitive_category_presence"][category] += 1

    normalized = _normalized_key(key_name)
    canonical = SENSITIVE_VALUE_KEY_ALIASES.get(normalized)
    if canonical is None and (normalized.endswith("token") or normalized in {"token", "jwt"}):
        canonical = safe_key
    if canonical:
        bucket["sensitive_value_states"][canonical][_value_state(value)] += 1

    if str(key_name) in SAFE_ROUTE_KEYS and isinstance(value, (str, int, bool)):
        bucket["safe_values"][str(key_name)][str(value)] += 1

    if str(key_name) == "payment_binding" and isinstance(value, dict):
        for payment_key, payment_value in value.items():
            if payment_key in SAFE_PAYMENT_KEYS and isinstance(payment_value, (str, int, bool)):
                bucket["payment_binding_safe"][payment_key][str(payment_value)] += 1


def _iter_json_candidates(text: str) -> Iterator[Any]:
    if not text or len(text) > 8_000_000:
        return
    decoder = json.JSONDecoder()
    seen_spans: Set[Tuple[int, int]] = set()
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            value, end = decoder.raw_decode(stripped)
            yield value
        except Exception:
            pass
    attempts = 0
    for match in re.finditer(r"[\{\[]", text):
        attempts += 1
        if attempts > 256:
            break
        try:
            value, end = decoder.raw_decode(text[match.start():])
        except Exception:
            continue
        span = (match.start(), match.start() + end)
        if span in seen_spans:
            continue
        seen_spans.add(span)
        yield value


def scan_payload_text(text: str, bucket: Dict[str, Any]) -> None:
    # Sensitive-category classification is intentionally based on parsed JSON/form
    # keys below, not arbitrary raw payload prose. This prevents false positives
    # such as Crashlytics `prompt_enabled` being labeled as a voice prompt.
    for event in SAFE_EVENT_VALUES:
        if re.search(rf'(?:(?:"|=)|\b){re.escape(event)}(?:(?:"|\b))', text, re.I):
            bucket["event_types"][event] += 1

    for parsed in _iter_json_candidates(text):
        for obj in iter_json_objects(parsed):
            if not isinstance(obj, dict):
                continue
            for key_name, value in obj.items():
                _record_key_value(bucket, key_name, value)

    # Cover form-urlencoded login/token requests without retaining values.
    if "=" in text and len(text) <= 1_000_000:
        try:
            for key_name, value in parse_qsl(text, keep_blank_values=True, strict_parsing=False):
                if key_name and len(key_name) <= 128:
                    _record_key_value(bucket, key_name, value)
        except Exception:
            pass


def _normalized_hostname(value: str) -> str:
    host = value.strip().lower().rstrip(".")
    if host.startswith("[") and "]" in host:
        return host[1:host.index("]")]
    if host.count(":") == 1:
        left, right = host.rsplit(":", 1)
        if right.isdigit():
            host = left
    return host


def sanitize_decrypted_payloads(
    pcap_paths: Sequence[Path],
    keylog_paths: Sequence[Path],
    target_hostnames: Set[str],
) -> Dict[str, Any]:
    tshark = find_tshark()
    aggregate: Dict[str, Any] = {
        "direction_model": "TLS_CLIENT_HELLO_SOURCE_PER_TCP_STREAM",
        "tshark_available": bool(tshark),
        "pcaps_scanned": 0,
        "streams_selected": 0,
        "records_scanned": 0,
        "records_scanned_by_direction": Counter(),
        "http_transactions": Counter(),
        "websocket_frames": Counter(),
        "directional": {
            DIRECTION_PHONE_TO_SERVER: _new_payload_bucket(),
            DIRECTION_SERVER_TO_PHONE: _new_payload_bucket(),
            DIRECTION_UNKNOWN: _new_payload_bucket(),
        },
    }
    endpoint_buckets: Dict[Tuple[str, str, str], Dict[str, Any]] = defaultdict(_new_payload_bucket)
    if not tshark:
        aggregate["endpoint_observations"] = []
        return normalize_counter_tree(aggregate)

    normalized_targets = {_normalized_hostname(host) for host in target_hostnames if host}
    keylog = next((path for path in keylog_paths if path.exists() and path.stat().st_size > 0), None)

    for pcap in pcap_paths:
        if not pcap.exists() or pcap.stat().st_size == 0:
            continue
        aggregate["pcaps_scanned"] += 1
        tls_args: List[str] = []
        if keylog:
            tls_args = ["-o", f"tls.keylog_file:{keylog}"]

        stream_host: Dict[str, str] = {}
        stream_client: Dict[str, str] = {}
        allowed_streams: Set[str] = set()
        for line in tshark_run(
            tshark,
            ["-r", str(pcap), *tls_args,
             "-Y", "tls.handshake.type == 1 && tls.handshake.extensions_server_name",
             "-T", "fields", "-E", "separator=\t", "-E", "occurrence=f",
             "-e", "tcp.stream", "-e", "ip.src", "-e", "ipv6.src",
             "-e", "tls.handshake.extensions_server_name"],
        ):
            fields = (line.split("\t") + [""] * 4)[:4]
            stream = fields[0].strip()
            source = (fields[1] or fields[2]).strip()
            host = _normalized_hostname(fields[3].split(",", 1)[0])
            if stream and host in normalized_targets:
                allowed_streams.add(stream)
                stream_host[stream] = host
                if source:
                    stream_client[stream] = source
        aggregate["streams_selected"] += len(allowed_streams)

        if allowed_streams:
            stream_filter_for_ws = " or ".join(
                f"tcp.stream=={stream}" for stream in sorted(
                    allowed_streams, key=lambda value: int(value) if value.isdigit() else 0
                )
            )
            opcode_names = {
                "0": "continuation", "1": "text", "2": "binary",
                "8": "close", "9": "ping", "10": "pong",
            }
            for line in tshark_run(
                tshark,
                ["-r", str(pcap), *tls_args, "-Y", f"({stream_filter_for_ws}) and websocket",
                 "-T", "fields", "-E", "separator=\t", "-E", "occurrence=f",
                 "-e", "tcp.stream", "-e", "ip.src", "-e", "ipv6.src",
                 "-e", "websocket.opcode"],
            ):
                fields = (line.split("\t") + [""] * 4)[:4]
                stream = fields[0].strip()
                source = (fields[1] or fields[2]).strip()
                opcode = fields[3].strip()
                client = stream_client.get(stream, "")
                if client and source == client:
                    ws_direction = DIRECTION_PHONE_TO_SERVER
                elif client and source:
                    ws_direction = DIRECTION_SERVER_TO_PHONE
                else:
                    ws_direction = DIRECTION_UNKNOWN
                host = stream_host.get(stream, "")
                aggregate["websocket_frames"][(
                    ws_direction, host, opcode_names.get(opcode, f"opcode_{opcode or 'unknown'}")
                )] += 1

        request_meta: Dict[Tuple[str, str], Dict[str, str]] = {}
        stream_last_request: Dict[str, Dict[str, str]] = {}
        for line in tshark_run(
            tshark,
            ["-r", str(pcap), *tls_args,
             "-Y", "http.request or http2.headers.method",
             "-T", "fields", "-E", "separator=\t", "-E", "occurrence=f",
             "-e", "frame.number", "-e", "tcp.stream", "-e", "http2.streamid",
             "-e", "http.host", "-e", "http.request.method", "-e", "http.request.uri",
             "-e", "http2.headers.authority", "-e", "http2.headers.method",
             "-e", "http2.headers.path"],
        ):
            fields = (line.split("\t") + [""] * 9)[:9]
            frame, stream, h2id = fields[0].strip(), fields[1].strip(), fields[2].strip()
            if allowed_streams and stream not in allowed_streams:
                continue
            host = _normalized_hostname(fields[3] or fields[6] or stream_host.get(stream, ""))
            if host not in normalized_targets:
                continue
            method = (fields[4] or fields[7]).strip()
            path = sanitize_path_template((fields[5] or fields[8]).strip())
            request_key = (stream, f"h2:{h2id}" if h2id else f"h1:{frame}")
            meta = {"hostname": host, "method": method, "path_template": path, "status": "unknown"}
            request_meta[request_key] = meta
            stream_last_request[stream] = meta

        for line in tshark_run(
            tshark,
            ["-r", str(pcap), *tls_args,
             "-Y", "http.response or http2.headers.status",
             "-T", "fields", "-E", "separator=\t", "-E", "occurrence=f",
             "-e", "tcp.stream", "-e", "http2.streamid", "-e", "http.request_in",
             "-e", "http.response.code", "-e", "http2.headers.status"],
        ):
            fields = (line.split("\t") + [""] * 5)[:5]
            stream, h2id, request_in = fields[0].strip(), fields[1].strip(), fields[2].strip()
            status = (fields[3] or fields[4]).strip() or "unknown"
            key = (stream, f"h2:{h2id}") if h2id else (stream, f"h1:{request_in}")
            if key in request_meta:
                request_meta[key]["status"] = status

        for meta in request_meta.values():
            aggregate["http_transactions"][(
                meta["hostname"], meta["method"], meta["path_template"], meta["status"]
            )] += 1

        if not allowed_streams:
            continue
        stream_filter = " or ".join(
            f"tcp.stream=={stream}" for stream in sorted(
                allowed_streams, key=lambda value: int(value) if value.isdigit() else 0
            )
        )
        display_filter = (
            f"({stream_filter}) and "
            "(websocket.payload or http.file_data or http2.data.data)"
        )
        for line in tshark_run(
            tshark,
            ["-r", str(pcap), *tls_args, "-Y", display_filter,
             "-T", "fields", "-E", "separator=\t", "-E", "occurrence=a", "-E", "aggregator=|",
             "-e", "tcp.stream", "-e", "http2.streamid", "-e", "ip.src", "-e", "ipv6.src",
             "-e", "websocket.payload", "-e", "http.file_data", "-e", "http2.data.data"],
        ):
            fields = (line.split("\t") + [""] * 7)[:7]
            stream, h2id = fields[0].strip(), fields[1].strip()
            source = (fields[2] or fields[3]).strip()
            client = stream_client.get(stream, "")
            if client and source == client:
                direction = DIRECTION_PHONE_TO_SERVER
            elif client and source:
                direction = DIRECTION_SERVER_TO_PHONE
            else:
                direction = DIRECTION_UNKNOWN

            endpoint = request_meta.get((stream, f"h2:{h2id}")) if h2id else None
            if endpoint is None:
                endpoint = stream_last_request.get(stream, {
                    "hostname": stream_host.get(stream, ""),
                    "path_template": "",
                })
            host = endpoint.get("hostname", stream_host.get(stream, ""))
            path_template = endpoint.get("path_template", "")

            for field in fields[4:]:
                if not field:
                    continue
                for value in field.split("|"):
                    if not value:
                        continue
                    data = decode_possible_hex(value)
                    text = data.decode("utf-8", errors="replace")
                    aggregate["records_scanned"] += 1
                    aggregate["records_scanned_by_direction"][direction] += 1
                    scan_payload_text(text, aggregate["directional"][direction])
                    scan_payload_text(text, endpoint_buckets[(direction, host, path_template)])

    endpoint_observations = []
    for (direction, host, path_template), bucket in sorted(endpoint_buckets.items()):
        normalized_bucket = normalize_counter_tree(bucket)
        endpoint_observations.append({
            "direction": direction,
            "hostname": host,
            "path_template": path_template,
            "sensitive_category_presence": normalized_bucket.get("sensitive_category_presence", {}),
            "sensitive_value_states": normalized_bucket.get("sensitive_value_states", {}),
            "event_types": normalized_bucket.get("event_types", {}),
            "safe_values": normalized_bucket.get("safe_values", {}),
            "payment_binding_safe": normalized_bucket.get("payment_binding_safe", {}),
        })
    aggregate["endpoint_observations"] = endpoint_observations
    return normalize_counter_tree(aggregate)


def sanitize_path_template(path: str) -> str:
    if not path:
        return ""
    path = path.split("?", 1)[0]
    segments = []
    for segment in path.split("/"):
        if not segment:
            segments.append("")
            continue
        firebase_app_id = bool(re.fullmatch(r"\d+:\d+:android:[0-9a-fA-F]+", segment))
        opaque_identifier = bool(
            re.fullmatch(r"[0-9a-fA-F-]{16,}", segment)
            or re.fullmatch(r"\d{6,}", segment)
            or re.fullmatch(r"[A-Za-z0-9_-]{32,}", segment)
            or (":" in segment and len(segment) >= 20 and re.fullmatch(r"[A-Za-z0-9:_-]+", segment))
        )
        if len(segment) > 48 or firebase_app_id or opaque_identifier:
            segments.append("{id}")
        elif re.search(r"preview_image_|upload|object", segment, re.I) and "." in segment:
            suffix = Path(segment).suffix
            segments.append("{object}" + suffix)
        else:
            segments.append(segment)
    return "/".join(segments)[:300]


def normalize_counter_tree(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(sorted(value.items(), key=lambda item: str(item[0])))
    if isinstance(value, defaultdict):
        return {str(k): normalize_counter_tree(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if key == "http_requests" and isinstance(child, Counter):
                result[key] = [
                    {"hostname": k[0], "method": k[1], "path_template": k[2], "count": count}
                    for k, count in sorted(child.items())
                ]
            elif key == "http_transactions" and isinstance(child, Counter):
                result[key] = [
                    {
                        "hostname": k[0],
                        "method": k[1],
                        "path_template": k[2],
                        "response_status": k[3],
                        "count": count,
                    }
                    for k, count in sorted(child.items())
                ]
            elif key == "websocket_frames" and isinstance(child, Counter):
                result[key] = [
                    {
                        "direction": k[0],
                        "hostname": k[1],
                        "opcode": k[2],
                        "count": count,
                    }
                    for k, count in sorted(child.items())
                ]
            else:
                result[str(key)] = normalize_counter_tree(child)
        return result
    if isinstance(value, list):
        return [normalize_counter_tree(item) for item in value]
    return value


def sanitize_phase(
    phase_id: str,
    private_phase: Path,
    sanitized_phase: Path,
    key: bytes,
    target_packages: Set[str],
    target_uids: Set[str],
) -> Dict[str, Any]:
    sanitized_phase.mkdir(parents=True, exist_ok=True)
    csv_paths = [p for p in private_phase.rglob("*.csv") if p.is_file()]
    pcap_paths = [p for p in private_phase.rglob("*") if p.is_file() and p.suffix.lower() in PCAP_SUFFIXES]
    keylog_paths = [
        p for p in private_phase.rglob("*")
        if p.is_file() and any(token in p.name.lower() for token in SSL_TOKENS)
    ]
    logcat_paths = [p for p in private_phase.rglob("*logcat*.txt") if p.is_file()]
    runtime_dirs = [p for p in private_phase.rglob("state-*") if p.is_dir()]

    network = summarize_connections_csv(csv_paths, key, target_packages, target_uids)
    payload = sanitize_decrypted_payloads(pcap_paths, keylog_paths, set(network["target_hostnames"]))
    logcat = sanitize_logcat(logcat_paths[0]) if logcat_paths else {"available": False, "events": {}}
    runtime = sanitize_runtime_state(private_phase, sorted(target_packages))

    result = {
        "schema": "rokid.test16.sanitized-phase.v1.2",
        "phase_id": phase_id,
        "private_raw_files_included": False,
        "raw_artifact_counts": {
            "pcap": len(pcap_paths),
            "ssl_keylog": len(keylog_paths),
            "connections_csv": len(csv_paths),
            "logcat": len(logcat_paths),
        },
        "network": network,
        "decrypted_payload_presence": payload,
        "logcat_event_summary": logcat,
        "runtime_summary": runtime,
    }
    write_json(sanitized_phase / "phase-summary.json", result)
    return result


def _privacy_iter_json_scalars(value: Any, path: Tuple[str, ...] = ()) -> Iterator[Tuple[Tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _privacy_iter_json_scalars(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _privacy_iter_json_scalars(child, (*path, str(index)))
    else:
        yield path, value


def _privacy_looks_like_phone_number(candidate: str, key_path: Tuple[str, ...]) -> bool:
    value = candidate.strip()
    key = key_path[-1].lower() if key_path else ""
    exempt_keys = {
        "version_name", "version_code", "android_release", "sdk", "schema",
        "test_id", "start_utc", "end_utc", "checked_utc", "duration_seconds",
        "snapshot_seconds", "count", "occurrences", "bytes_sent", "bytes_received",
        "packets_sent", "packets_received", "connections", "size", "status_code",
        "destination_port", "standby_bucket",
    }
    exempt_suffixes = (
        "_sha256", "_hmac", "_utc", "_time", "_timestamp", "_seconds",
        "_count", "_bytes", "_size", "_code", "_version", "_bucket",
    )
    if key in exempt_keys or key.endswith(exempt_suffixes):
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ].*)?", value):
        return False
    if re.fullmatch(r"(?:[A-Za-z]+\s*)?\d+(?:\.\d+){2,}", value):
        return False
    if re.fullmatch(r"\d+(?:-\d+){2,}(?:-\d+)?", value):
        return False
    digits = re.sub(r"\D", "", value)
    if not (7 <= len(digits) <= 15):
        return False
    if value.startswith("+"):
        return True
    if re.fullmatch(r"\d{10,15}", value):
        return True
    if re.search(r"[ ()-]", value):
        groups = [group for group in re.split(r"\D+", value) if group]
        return len(groups) >= 2 and all(1 <= len(group) <= 4 for group in groups)
    return False


def privacy_gate(root: Path) -> Dict[str, Any]:
    forbidden_suffixes = {
        ".pcap", ".pcapng", ".cap", ".keylog", ".keys", ".har",
        ".jpg", ".jpeg", ".png", ".webp", ".heic", ".mp4", ".mov",
        ".apk", ".apks", ".aab", ".so",
    }
    patterns = {
        "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
        "mac_address": re.compile(r"\b(?:[0-9A-F]{2}:){5}[0-9A-F]{2}\b", re.I),
        "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "user_home_path": re.compile(r"/Users/[^/\s]+"),
        "url_query": re.compile(r"https?://\S+\?\S+"),
        "bearer": re.compile(r"\bBearer\s+[A-Za-z0-9._~-]+", re.I),
        "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "precise_coordinate": re.compile(
            r'(?i)(latitude|longitude|"\s*(lat|lon|lng)\s*")\s*[:=]\s*-?\d{1,3}\.\d{4,}'
        ),
        "firebase_app_id": re.compile(r"\b\d+:\d+:android:[0-9a-fA-F]{8,}\b"),
        "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    }
    phone_candidate = re.compile(r"(?<![A-Za-z0-9])\+?\d[\d .()_-]{6,}\d(?![A-Za-z0-9])")
    violations: List[Dict[str, str]] = []

    for path in root.rglob("*"):
        if not path.is_file() or path.name in {"PRIVACY_GATE.json", "SHA256SUMS.txt"}:
            continue
        relative = str(path.relative_to(root))
        if path.suffix.lower() in forbidden_suffixes:
            violations.append({"file": relative, "type": "forbidden_file_type"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            violations.append({"file": relative, "type": "non_text_binary"})
            continue
        for name, pattern in patterns.items():
            if pattern.search(text):
                violations.append({"file": relative, "type": name})

        if path.suffix.lower() == ".json":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                violations.append({"file": relative, "type": "invalid_json"})
                continue
            for key_path, value in _privacy_iter_json_scalars(parsed):
                if not isinstance(value, str):
                    continue
                for match in phone_candidate.finditer(value):
                    if _privacy_looks_like_phone_number(match.group(0), key_path):
                        violations.append({
                            "file": relative,
                            "type": "phone_number",
                            "json_path": ".".join(key_path),
                        })
                        break

    result = {
        "schema": "rokid.test16.privacy-gate.v1.1",
        "pass": not violations,
        "violations": violations,
        "checked_utc": utc_now(),
    }
    write_json(root / "PRIVACY_GATE.json", result)
    return result

def write_manifest(root: Path, filename: str = "SHA256SUMS.txt") -> Path:
    destination = root / filename
    lines = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path != destination:
            lines.append(f"{sha256_file(path)}  {path.relative_to(root)}")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination


def make_zip(root: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=f"{root.name}/{path.relative_to(root)}")


def package_sanitized_upload(
    sanitized_root: Path,
    destination: Path,
) -> Dict[str, Any]:
    gate = privacy_gate(sanitized_root)
    if not gate["pass"]:
        raise TestAbort(f"Sanitized privacy gate failed: {gate['violations']}")
    write_manifest(sanitized_root)
    make_zip(sanitized_root, destination)
    return {
        "zip": str(destination),
        "sha256": sha256_file(destination),
        "privacy_gate": "PASS",
    }


def capture_phase_interactive(
    base: Sequence[str],
    user_id: str,
    phase_id: str,
    private_phase: Path,
    duration_seconds: int,
    action_prompt: str,
    target_packages: Set[str],
    target_uids: Set[str],
    screen_off: bool = False,
    require_ssl_keylog: bool = False,
    required_export_kinds: Optional[Set[str]] = None,
    snapshot_seconds: int = 20,
    pre_action_commands: Optional[Sequence[Sequence[str]]] = None,
    post_action_commands: Optional[Sequence[Sequence[str]]] = None,
) -> Dict[str, Any]:
    private_phase.mkdir(parents=True, exist_ok=True)
    collection_uri, before_rows = query_media_store(base, user_id)
    baseline_ids = media_ids(before_rows)
    start_epoch = int(time.time())

    run([*base, "logcat", "-c"], check=False)
    logcat = start_logcat(base, private_phase / "logcat-private.txt")
    collect_target_runtime_state(
        base, private_phase / "state-before", sorted(target_packages), "before"
    )

    try:
        adb_shell(
            base, "monkey", "-p", PCAPDROID, "-c",
            "android.intent.category.LAUNCHER", "1", check=False
        )
        prompt_enter(
            "Start a NEW PCAPdroid capture. Set App Filter to Hi Rokid "
            "(com.rokid.sprite.global.aiapp), enable TLS decryption, and confirm the "
            "Hi Rokid APP decryption rule is enabled. Keep Block QUIC enabled for this "
            "controlled decryption run. Confirm recording is active."
        )

        for command in pre_action_commands or ():
            run(command, check=False)
            time.sleep(1)

        prompt_enter(action_prompt)

        for command in post_action_commands or ():
            run(command, check=False)
            time.sleep(1)

        if screen_off:
            prompt_enter(
                "Lock the PHONE screen now. Keep Bluetooth and internet unchanged. "
                "Do not interact until the timer ends."
            )

        started = time.monotonic()
        next_snapshot = 0
        snapshot_index = 0
        while True:
            elapsed = int(time.monotonic() - started)
            remaining = duration_seconds - elapsed
            if remaining <= 0:
                break
            if snapshot_seconds > 0 and elapsed >= next_snapshot:
                collect_target_runtime_state(
                    base,
                    private_phase / "state-snapshots" / f"snapshot-{snapshot_index:03d}",
                    sorted(target_packages),
                    f"tplus-{elapsed:04d}s",
                )
                snapshot_index += 1
                next_snapshot += snapshot_seconds
            print(f"\r{phase_id}: {remaining:3d}s remaining", end="", flush=True)
            time.sleep(min(5, remaining))
        print(f"\r{phase_id}: observation complete.    ")

        if screen_off:
            prompt_enter("Unlock the phone without opening Hi Rokid.")

        prompt_enter(
            "Stop PCAPdroid and export: packet capture, SSL key log, and connections CSV. "
            "For a deliberately force-stopped zero-traffic phase, PCAPdroid may delete an "
            "empty PCAP; continue because logcat and periodic runtime snapshots remain valid."
        )
        exports = pull_phase_exports(
            base, user_id, collection_uri, baseline_ids, start_epoch,
            private_phase / "pcapdroid-private"
        )
        write_json(private_phase / "exports-private.json", exports)
        export_kinds = {item.get("kind") for item in exports}
        required = set(required_export_kinds or set())
        if require_ssl_keylog:
            required.add("ssl_keylog")
        missing = sorted(required - export_kinds)
        if missing:
            raise TestAbort(
                f"{phase_id}: required PCAPdroid exports are missing: {', '.join(missing)}. "
                "The private phase was retained. Do not continue until the Hi Rokid app "
                "decryption rule is active, green open-lock connections are visible, and "
                "PCAP + SSL key log + connections CSV are exported."
            )
    finally:
        stop_logcat(logcat)

    collect_target_runtime_state(
        base, private_phase / "state-after", sorted(target_packages), "after"
    )
    key, _ = get_privacy_key()
    sanitized_phase = private_phase.parents[2] / "sanitized-upload" / "phases" / private_phase.name
    result = sanitize_phase(
        phase_id, private_phase, sanitized_phase, key, target_packages, target_uids
    )
    return result
