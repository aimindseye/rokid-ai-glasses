#!/usr/bin/env python3
"""Test 16D — Pixel Background Mode A/B.

Compares the already-paired Pixel before and after enabling Hi Rokid's
"Allow Rokid App to run in the background" setting. It does not repeat login,
pairing, voice AI, visual AI, or media transfer. It never restarts, power-cycles,
or factory-resets the glasses.

Raw packet captures, TLS keys, logcat, IP addresses, device identifiers, account
data, and payload values remain private. Only a privacy-gated sanitized ZIP is
intended for upload.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import signal
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from test16_common import (
    HI_ROKID,
    PCAPDROID,
    PCAP_SUFFIXES,
    SSL_TOKENS,
    TestAbort,
    _new_payload_bucket,
    adb_base,
    adb_shell,
    ask_yes_no,
    classify_export,
    collect_package_inventory,
    collect_sanitized_permission_state,
    collect_target_runtime_state,
    decode_possible_hex,
    discover_pixel_serial,
    find_tshark,
    get_privacy_key,
    media_ids,
    normalize_counter_tree,
    package_details,
    package_sanitized_upload,
    prompt_enter,
    pseudonym,
    pull_phase_exports,
    query_media_store,
    run,
    sanitize_phase,
    sanitize_runtime_state,
    scan_payload_text,
    sha256_file,
    start_logcat,
    stop_logcat,
    tshark_run,
    utc_now,
    validate_pixel,
    write_json,
)

BUCKET_NAMES = {
    5: "exempted",
    10: "active",
    20: "working_set",
    30: "frequent",
    40: "rare",
    45: "restricted",
    50: "never",
}


def marker(base: Sequence[str], label: str) -> None:
    adb_shell(base, "log", "-t", "RokidTest16D", label, check=False)


def _appop_mode(text: str) -> str:
    modes = re.findall(r"(?:^|:)\s*(allow|deny|ignore|foreground|default)\b", text, re.I | re.M)
    if modes:
        return modes[-1].lower()
    match = re.search(r"Default mode:\s*(\w+)", text, re.I)
    return match.group(1).lower() if match else "unknown"


def _active_notification_present(notification_text: str) -> bool:
    active = notification_text.split("mArchive=", 1)[0]
    return (
        HI_ROKID in active
        and ("ai_service_channel" in active or "Rokid AI service is running" in active)
        and ("FOREGROUND_SERVICE" in active or "flags=0x00000040" in active)
    )


def collect_background_controls(
    base: Sequence[str],
    uid: str,
    private_dir: Path,
) -> Dict[str, Any]:
    private_dir.mkdir(parents=True, exist_ok=True)
    commands = {
        "appops-run-in-background.txt": [*base, "shell", "cmd", "appops", "get", HI_ROKID, "RUN_IN_BACKGROUND"],
        "appops-run-any-in-background.txt": [*base, "shell", "cmd", "appops", "get", HI_ROKID, "RUN_ANY_IN_BACKGROUND"],
        "appops-start-foreground.txt": [*base, "shell", "cmd", "appops", "get", HI_ROKID, "START_FOREGROUND"],
        "standby-bucket.txt": [*base, "shell", "am", "get-standby-bucket", HI_ROKID],
        "inactive.txt": [*base, "shell", "am", "get-inactive", HI_ROKID],
        "deviceidle-whitelist.txt": [*base, "shell", "dumpsys", "deviceidle", "whitelist"],
        "package.txt": [*base, "shell", "dumpsys", "package", HI_ROKID],
        "process.txt": [*base, "shell", "sh", "-c", f"ps -A -o USER,PID,PPID,NAME,ARGS 2>&1 | grep -F '{HI_ROKID}' || true"],
        "services.txt": [*base, "shell", "dumpsys", "activity", "services", HI_ROKID],
        "notifications.txt": [*base, "shell", "dumpsys", "notification", "--noredact"],
        "companion.txt": [*base, "shell", "dumpsys", "companiondevice"],
        "power-saving.txt": [*base, "shell", "settings", "get", "global", "low_power"],
        "data-saver.txt": [*base, "shell", "cmd", "netpolicy", "get", "restrict-background"],
        "netpolicy-whitelist.txt": [*base, "shell", "cmd", "netpolicy", "list", "restrict-background-whitelist"],
        "netpolicy-blacklist.txt": [*base, "shell", "cmd", "netpolicy", "list", "restrict-background-blacklist"],
    }
    outputs: Dict[str, str] = {}
    for name, command in commands.items():
        result = run(command, check=False)
        text = (result.stdout or "") + (result.stderr or "")
        outputs[name] = text
        (private_dir / name).write_text(text, encoding="utf-8")

    try:
        bucket = int(outputs["standby-bucket.txt"].strip().splitlines()[-1])
    except Exception:
        bucket = -1

    package_text = outputs["package.txt"]
    services_text = outputs["services.txt"]
    process_text = outputs["process.txt"]
    companion_text = outputs["companion.txt"]
    whitelist_text = outputs["deviceidle-whitelist.txt"]
    uid_pattern = re.compile(rf"(?<!\d){re.escape(uid)}(?!\d)") if uid else re.compile(r"a^")

    post_notifications_match = re.search(
        r"android\.permission\.POST_NOTIFICATIONS:\s+granted=(true|false)",
        package_text,
        re.I,
    )
    stopped_match = re.search(r"\bstopped=(true|false)", package_text, re.I)

    return {
        "run_in_background": _appop_mode(outputs["appops-run-in-background.txt"]),
        "run_any_in_background": _appop_mode(outputs["appops-run-any-in-background.txt"]),
        "start_foreground": _appop_mode(outputs["appops-start-foreground.txt"]),
        "standby_bucket": bucket,
        "standby_bucket_name": BUCKET_NAMES.get(bucket, "unknown"),
        "inactive": "true" in outputs["inactive.txt"].lower(),
        "device_idle_allowlisted": HI_ROKID in whitelist_text,
        "post_notifications_granted": (
            post_notifications_match.group(1).lower() == "true"
            if post_notifications_match else None
        ),
        "package_stopped": (
            stopped_match.group(1).lower() == "true" if stopped_match else None
        ),
        "process_active": HI_ROKID in process_text,
        "active_service_record": "ServiceRecord" in services_text and HI_ROKID in services_text,
        "ai_service_active": "AiService" in services_text,
        "location_service_active": "LocationService" in services_text,
        "foreground_ai_notification_active": _active_notification_present(outputs["notifications.txt"]),
        "companion_association_present": HI_ROKID in companion_text,
        "power_saving_enabled": outputs["power-saving.txt"].strip() == "1",
        "data_saver_enabled": "enabled" in outputs["data-saver.txt"].lower(),
        "data_saver_whitelisted": bool(uid and uid_pattern.search(outputs["netpolicy-whitelist.txt"])),
        "data_saver_blacklisted": bool(uid and uid_pattern.search(outputs["netpolicy-blacklist.txt"])),
    }


def control_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    changed = {}
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changed[key] = {"before": before.get(key), "after": after.get(key)}
    return {"changed_count": len(changed), "changed": changed}


def wait_with_snapshots(
    base: Sequence[str],
    private_phase: Path,
    segment: str,
    duration: int,
    snapshot_seconds: int,
    target_packages: Set[str],
) -> None:
    started = time.monotonic()
    next_snapshot = 0
    index = 0
    while True:
        elapsed = int(time.monotonic() - started)
        remaining = duration - elapsed
        if remaining <= 0:
            break
        if elapsed >= next_snapshot:
            collect_target_runtime_state(
                base,
                private_phase / "state-segments" / segment / f"snapshot-{index:03d}",
                sorted(target_packages),
                f"{segment}-tplus-{elapsed:04d}s",
            )
            index += 1
            next_snapshot += snapshot_seconds
        print(f"\r{segment}: {remaining:3d}s remaining", end="", flush=True)
        time.sleep(min(5, remaining))
    print(f"\r{segment}: observation complete.    ")


def _phase_files(private_phase: Path) -> Tuple[List[Path], List[Path], List[Path]]:
    pcaps = [p for p in private_phase.rglob("*") if p.is_file() and p.suffix.lower() in PCAP_SUFFIXES]
    keylogs = [p for p in private_phase.rglob("*") if p.is_file() and any(t in p.name.lower() for t in SSL_TOKENS)]
    csvs = [p for p in private_phase.rglob("*.csv") if p.is_file()]
    return pcaps, keylogs, csvs


def sanitize_segmented_transport(
    private_phase: Path,
    segments: List[Dict[str, Any]],
    target_hostnames: Set[str],
) -> Dict[str, Any]:
    tshark = find_tshark()
    pcaps, keylogs, _ = _phase_files(private_phase)
    result: Dict[str, Any] = {
        "tshark_available": bool(tshark),
        "pcaps_scanned": len(pcaps),
        "segments": [],
    }
    if not tshark or not pcaps:
        return result
    keylog = next((p for p in keylogs if p.stat().st_size > 0), None)
    normalized_targets = {h.lower().rstrip(".") for h in target_hostnames if h}

    for pcap in pcaps:
        tls_args: List[str] = ["-o", f"tls.keylog_file:{keylog}"] if keylog else []
        stream_host: Dict[str, str] = {}
        stream_client: Dict[str, str] = {}
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
            client = (fields[1] or fields[2]).strip()
            host = fields[3].split(",", 1)[0].strip().lower().rstrip(".")
            if stream and (not normalized_targets or host in normalized_targets):
                stream_host[stream] = host
                stream_client[stream] = client

        for segment in segments:
            start_epoch = float(segment["start_epoch"])
            end_epoch = float(segment["end_epoch"])
            filt = f"frame.time_epoch >= {start_epoch:.6f} && frame.time_epoch < {end_epoch:.6f}"
            counters = {
                "frames": 0,
                "frame_bytes": 0,
                "payload_bytes": 0,
                "tcp_syn": 0,
                "tcp_fin": 0,
                "tcp_reset": 0,
                "zero_payload_tcp_frames": 0,
            }
            endpoint_counts: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(
                lambda: {"frames": 0, "frame_bytes": 0, "payload_bytes": 0}
            )
            ws_counter: Counter = Counter()
            directional_payload = {
                "PHONE_TO_SERVER": _new_payload_bucket(),
                "SERVER_TO_PHONE": _new_payload_bucket(),
                "UNKNOWN": _new_payload_bucket(),
            }
            opcode_names = {
                "0": "continuation", "1": "text", "2": "binary",
                "8": "close", "9": "ping", "10": "pong",
            }

            for line in tshark_run(
                tshark,
                ["-r", str(pcap), *tls_args, "-Y", filt,
                 "-T", "fields", "-E", "separator=\t", "-E", "occurrence=a", "-E", "aggregator=|",
                 "-e", "frame.len", "-e", "tcp.stream", "-e", "ip.src", "-e", "ipv6.src",
                 "-e", "tcp.len", "-e", "udp.length", "-e", "tcp.flags.syn",
                 "-e", "tcp.flags.fin", "-e", "tcp.flags.reset", "-e", "websocket.opcode",
                 "-e", "websocket.payload", "-e", "http.file_data", "-e", "http2.data.data"],
            ):
                fields = (line.split("\t") + [""] * 13)[:13]
                try: frame_len = int(fields[0] or 0)
                except ValueError: frame_len = 0
                stream = fields[1].strip()
                source = (fields[2] or fields[3]).strip()
                try: tcp_len = int(fields[4] or 0)
                except ValueError: tcp_len = 0
                try: udp_len = int(fields[5] or 0)
                except ValueError: udp_len = 0
                payload_len = tcp_len + udp_len
                client = stream_client.get(stream, "")
                if client and source == client:
                    direction = "PHONE_TO_SERVER"
                elif client and source:
                    direction = "SERVER_TO_PHONE"
                else:
                    direction = "UNKNOWN"
                host = stream_host.get(stream, "unknown")

                counters["frames"] += 1
                counters["frame_bytes"] += frame_len
                counters["payload_bytes"] += payload_len
                counters["tcp_syn"] += 1 if fields[6] == "1" else 0
                counters["tcp_fin"] += 1 if fields[7] == "1" else 0
                counters["tcp_reset"] += 1 if fields[8] == "1" else 0
                if stream and tcp_len == 0:
                    counters["zero_payload_tcp_frames"] += 1
                endpoint_counts[(direction, host)]["frames"] += 1
                endpoint_counts[(direction, host)]["frame_bytes"] += frame_len
                endpoint_counts[(direction, host)]["payload_bytes"] += payload_len

                for opcode in (fields[9].split("|") if fields[9] else []):
                    ws_counter[(direction, host, opcode_names.get(opcode, f"opcode_{opcode}"))] += 1
                for raw_field in fields[10:13]:
                    if not raw_field:
                        continue
                    for value in raw_field.split("|"):
                        if value:
                            text = decode_possible_hex(value).decode("utf-8", errors="replace")
                            scan_payload_text(text, directional_payload[direction])

            result["segments"].append({
                "segment": segment["name"],
                "duration_seconds": int(end_epoch - start_epoch),
                "transport": counters,
                "endpoints": [
                    {
                        "direction": direction,
                        "hostname": host,
                        **counts,
                    }
                    for (direction, host), counts in sorted(endpoint_counts.items())
                ],
                "websocket_frames": [
                    {"direction": key[0], "hostname": key[1], "opcode": key[2], "count": count}
                    for key, count in sorted(ws_counter.items())
                ],
                "decrypted_payload_presence": {
                    direction: normalize_counter_tree(bucket)
                    for direction, bucket in directional_payload.items()
                },
            })
    return result


def run_background_arm(
    base: Sequence[str],
    user_id: str,
    arm_id: str,
    private_phase: Path,
    sanitized_root: Path,
    target_packages: Set[str],
    target_uids: Set[str],
    idle_seconds: int,
    recents_seconds: int,
    screen_off_seconds: int,
    snapshot_seconds: int,
) -> Dict[str, Any]:
    private_phase.mkdir(parents=True, exist_ok=True)
    collection_uri, before_rows = query_media_store(base, user_id)
    baseline_ids = media_ids(before_rows)
    phase_start_epoch = int(time.time())
    run([*base, "logcat", "-c"], check=False)
    logcat = start_logcat(base, private_phase / "logcat-private.txt")
    collect_target_runtime_state(base, private_phase / "state-before", sorted(target_packages), "before")
    segments: List[Dict[str, Any]] = []

    try:
        adb_shell(base, "monkey", "-p", PCAPDROID, "-c", "android.intent.category.LAUNCHER", "1", check=False)
        prompt_enter(
            f"{arm_id}: Start a NEW PCAPdroid capture with App Filter = Hi Rokid, the Hi Rokid "
            "app decryption rule enabled, TLS decryption enabled, Block QUIC enabled, and "
            "dump mode = PCAP file. Confirm recording is active."
        )
        adb_shell(base, "am", "force-stop", HI_ROKID, check=False)
        time.sleep(1)
        adb_shell(base, "monkey", "-p", HI_ROKID, "-c", "android.intent.category.LAUNCHER", "1", check=False)
        prompt_enter(
            f"{arm_id}: Wait for Hi Rokid to show the already-paired glasses with live battery "
            "information. Confirm a green open-lock connection in PCAPdroid. Do not use voice AI, "
            "visual AI, gallery import, navigation, translation, or recording."
        )
        idle_start = time.time(); marker(base, f"{arm_id}_IDLE_START")
        wait_with_snapshots(base, private_phase, "paired-idle", idle_seconds, snapshot_seconds, target_packages)
        idle_end = time.time(); segments.append({"name": "paired_idle", "start_epoch": idle_start, "end_epoch": idle_end})

        prompt_enter(
            f"{arm_id}: Open Android Recents and swipe Hi Rokid away. Do NOT force-stop it. "
            "Return here immediately after the task disappears."
        )
        recents_start = time.time(); marker(base, f"{arm_id}_RECENTS_DISMISSED")
        wait_with_snapshots(base, private_phase, "recents-dismissed-screen-on", recents_seconds, snapshot_seconds, target_packages)
        recents_end = time.time(); segments.append({"name": "recents_dismissed_screen_on", "start_epoch": recents_start, "end_epoch": recents_end})
        notification_after_swipe = ask_yes_no(
            f"{arm_id}: Is a Rokid AI Service foreground notification visible after the screen-on wait?"
        )

        prompt_enter(
            f"{arm_id}: Lock the PHONE screen now. Keep Bluetooth, Wi-Fi, and glasses state unchanged. "
            "Do not interact with the phone or glasses until the timer ends."
        )
        screen_start = time.time(); marker(base, f"{arm_id}_SCREEN_OFF_START")
        wait_with_snapshots(base, private_phase, "recents-dismissed-screen-off", screen_off_seconds, snapshot_seconds, target_packages)
        screen_end = time.time(); segments.append({"name": "recents_dismissed_screen_off", "start_epoch": screen_start, "end_epoch": screen_end})
        prompt_enter(f"{arm_id}: Unlock the phone without opening Hi Rokid.")
        notification_after_unlock = ask_yes_no(
            f"{arm_id}: Is the Rokid AI Service foreground notification visible after unlock?"
        )

        prompt_enter(
            f"{arm_id}: Stop PCAPdroid and export the packet capture, SSL key log, and connections CSV."
        )
        exports = pull_phase_exports(
            base, user_id, collection_uri, baseline_ids, phase_start_epoch,
            private_phase / "pcapdroid-private",
        )
        write_json(private_phase / "exports-private.json", exports)
        export_kinds = {item.get("kind") for item in exports}
        missing = sorted({"pcap", "ssl_keylog", "sidecar"} - export_kinds)
        if missing:
            raise TestAbort(
                f"{arm_id}: missing required PCAPdroid exports: {', '.join(missing)}. "
                "The private phase was retained; do not repeat other phases."
            )
    finally:
        stop_logcat(logcat)

    collect_target_runtime_state(base, private_phase / "state-after", sorted(target_packages), "after")
    key, _ = get_privacy_key()
    sanitized_phase = sanitized_root / "phases" / private_phase.name
    whole = sanitize_phase(arm_id, private_phase, sanitized_phase, key, target_packages, target_uids)
    segmented = sanitize_segmented_transport(
        private_phase,
        segments,
        set(whole.get("network", {}).get("target_hostnames", [])),
    )
    segmented["runtime_by_segment"] = {
        segment["name"]: sanitize_runtime_state(
            private_phase / "state-segments" / (
                "paired-idle" if segment["name"] == "paired_idle"
                else "recents-dismissed-screen-on" if segment["name"] == "recents_dismissed_screen_on"
                else "recents-dismissed-screen-off"
            ),
            sorted(target_packages),
        )
        for segment in segments
    }
    segmented["operator_observations"] = {
        "ai_service_notification_after_recents_wait": notification_after_swipe,
        "ai_service_notification_after_screen_off_unlock": notification_after_unlock,
    }
    write_json(sanitized_phase / "segmented-background-summary.json", segmented)
    return {
        "whole_phase": whole,
        "segmented": segmented,
        "operator_observations": segmented["operator_observations"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Privacy-first Pixel Background Mode A/B test for Hi Rokid."
    )
    parser.add_argument("--serial")
    parser.add_argument("--idle-minutes", type=float, default=1.0)
    parser.add_argument("--observe-minutes", type=float, default=3.0)
    parser.add_argument("--screen-off-minutes", type=float, default=3.0)
    parser.add_argument("--control-minutes", type=float, default=2.0)
    parser.add_argument("--snapshot-seconds", type=int, default=20)
    parser.add_argument("--output")
    args = parser.parse_args()

    serial = args.serial or discover_pixel_serial()
    base = adb_base(serial)
    device = validate_pixel(base)
    user_id = device["current_user"]
    root = (
        Path(args.output).expanduser().resolve()
        if args.output else Path.home() / "rokid-nettest" / "tests" /
        f"16d-pixel-background-ab-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    private_root = root / "private-raw-DO-NOT-UPLOAD"
    sanitized_root = root / "sanitized-upload"
    private_root.mkdir(parents=True)
    sanitized_root.mkdir(parents=True)

    key, key_path = get_privacy_key()
    inventory_before = collect_package_inventory(
        base, private_root / "inventories" / "start-packages-private.txt"
    )
    if HI_ROKID not in inventory_before:
        raise TestAbort("Hi Rokid is not installed on the Pixel.")
    details = package_details(
        base, HI_ROKID, private_root / "inventories" / "hi-rokid-private.txt"
    )
    uid = inventory_before[HI_ROKID].get("uid", "") or details.get("uid", "")
    target_packages = {HI_ROKID}
    target_uids = {uid} if uid else set()

    idle_seconds = max(30, int(args.idle_minutes * 60))
    observe_seconds = max(60, int(args.observe_minutes * 60))
    screen_seconds = max(60, int(args.screen_off_minutes * 60))
    control_seconds = max(60, int(args.control_minutes * 60))
    snapshots = max(10, int(args.snapshot_seconds))

    run_info: Dict[str, Any] = {
        "schema": "rokid.test16d.sanitized.v1",
        "test_id": "16d-pixel-background-mode-ab",
        "start_utc": utc_now(),
        "phone": {
            "model": device["model"],
            "android_release": device["android_release"],
            "sdk": device["sdk"],
            "device_serial_hmac": pseudonym(key, "device", device["serial"]),
        },
        "hi_rokid": {
            "package": HI_ROKID,
            "version_name": details.get("version_name", ""),
            "version_code": details.get("version_code", ""),
            "uid_hmac": pseudonym(key, "uid", uid) if uid else "",
        },
        "controls": {
            "glasses_already_paired_to_pixel": True,
            "login_repeated": False,
            "pairing_repeated": False,
            "voice_or_visual_ai_repeated": False,
            "glasses_restart_or_power_cycle_permitted": False,
            "factory_reset_permitted": False,
            "same_actions_before_and_after_background_enable": True,
            "pcapdroid_app_filter": HI_ROKID,
            "tls_decryption_required": True,
            "block_quic": True,
            "segment_runtime_snapshots_seconds": snapshots,
        },
        "privacy": {
            "private_raw_uploaded": False,
            "sensitive_values_retained_in_upload": False,
            "redaction_key_stored_locally": True,
            "redaction_key_filename": key_path.name,
        },
    }
    write_json(sanitized_root / "run-info.json", run_info)
    write_json(
        sanitized_root / "permissions-start.json",
        collect_sanitized_permission_state(
            base, HI_ROKID,
            private_root / "permissions" / "start-dumpsys-private.txt",
        ),
    )

    prompt_enter(
        "PREPARATION: The glasses must already be paired to this Pixel and remain powered and stable. "
        "Do not unbind, restart, power-cycle, or factory-reset them. Do not use voice AI, visual AI, "
        "gallery import, navigation, translation, or recording during this test. Confirm PCAPdroid "
        "still has App Filter = Hi Rokid, the Hi Rokid decryption rule, TLS decryption, Block QUIC, "
        "and PCAP file output enabled."
    )

    before_controls = collect_background_controls(
        base, uid, private_root / "background-controls" / "A-before"
    )
    write_json(sanitized_root / "background-controls-A-before.json", before_controls)

    arm_a = run_background_arm(
        base, user_id, "A_BACKGROUND_NOT_ENABLED",
        private_root / "phases" / "A-background-not-enabled",
        sanitized_root, target_packages, target_uids,
        idle_seconds, observe_seconds, screen_seconds, snapshots,
    )

    # Enable the in-app requested background mode outside packet capture.
    adb_shell(base, "am", "force-stop", HI_ROKID, check=False)
    adb_shell(base, "monkey", "-p", HI_ROKID, "-c", "android.intent.category.LAUNCHER", "1", check=False)
    prompt_enter(
        "SETTING TRANSITION: In Hi Rokid, tap the banner 'Go to enable'. On the Android screen it opens, "
        "enable the requested background operation setting. On Pixel this will commonly mean selecting "
        "Unrestricted under App battery usage. Do not alter Contacts, Calendar, Notification access, "
        "Location, Microphone, Camera, media, or any other permission. Return to Hi Rokid afterward."
    )
    transition_observations = {
        "go_to_enable_tapped": ask_yes_no("Did you tap Hi Rokid's 'Go to enable' button?", default=True),
        "android_app_battery_usage_screen_opened": ask_yes_no("Did Android open an App battery usage/background screen?", default=True),
        "unrestricted_selected": ask_yes_no("Did you select Unrestricted?", default=True),
        "other_permission_or_setting_changed": ask_yes_no("Did you change any other permission or setting?"),
        "background_banner_removed_or_satisfied": ask_yes_no("After returning, was the background-run banner removed or satisfied?", default=True),
    }
    if transition_observations["other_permission_or_setting_changed"]:
        raise TestAbort("A non-background setting was changed; preserve this run and do not continue B.")
    write_json(sanitized_root / "background-enable-operator-observations.json", transition_observations)
    after_controls = collect_background_controls(
        base, uid, private_root / "background-controls" / "B-after-enable"
    )
    write_json(sanitized_root / "background-controls-B-after.json", after_controls)
    diff = control_diff(before_controls, after_controls)
    write_json(sanitized_root / "background-controls-diff.json", diff)

    arm_b = run_background_arm(
        base, user_id, "B_BACKGROUND_ENABLED",
        private_root / "phases" / "B-background-enabled",
        sanitized_root, target_packages, target_uids,
        idle_seconds, observe_seconds, screen_seconds, snapshots,
    )

    # Force-stop boundary after enabled arm. Zero traffic is allowed.
    from test16_common import capture_phase_interactive
    force_stop_result = capture_phase_interactive(
        base, user_id, "D_FORCE_STOP_CONTROL",
        private_root / "phases" / "D-force-stop-control",
        control_seconds,
        "Hi Rokid has been force-stopped by the script. Do not reopen it. Leave the screen on and idle.",
        target_packages, target_uids,
        required_export_kinds=set(),
        snapshot_seconds=snapshots,
        pre_action_commands=[[*base, "shell", "am", "force-stop", HI_ROKID]],
    )
    force_stop_observations = {
        "ai_service_notification_gone": ask_yes_no("After force-stop, was the AI Service notification gone?", default=True),
        "glasses_connection_lost_or_unavailable": ask_yes_no("After force-stop, did the glasses connection become unavailable?", default=True),
    }
    write_json(sanitized_root / "force-stop-operator-observations.json", force_stop_observations)

    relaunch_result = capture_phase_interactive(
        base, user_id, "E_RELAUNCH_CONTROL",
        private_root / "phases" / "E-relaunch-control",
        control_seconds,
        "Hi Rokid has been relaunched. Wait for the already-paired glasses connection and live battery information. "
        "Confirm a green open-lock connection in PCAPdroid. Do not invoke AI or another feature.",
        target_packages, target_uids,
        required_export_kinds={"pcap", "ssl_keylog", "sidecar"},
        snapshot_seconds=snapshots,
        pre_action_commands=[[
            *base, "shell", "monkey", "-p", HI_ROKID,
            "-c", "android.intent.category.LAUNCHER", "1",
        ]],
    )
    relaunch_observations = {
        "transient_not_connected_popup": ask_yes_no("Did a transient 'not connected' popup appear?"),
        "ai_service_notification_started": ask_yes_no("Did the AI Service notification start?", default=True),
        "glasses_reconnected": ask_yes_no("Did the glasses reconnect?", default=True),
        "live_battery_returned": ask_yes_no("Did live battery information return?", default=True),
    }
    write_json(sanitized_root / "relaunch-operator-observations.json", relaunch_observations)

    final_controls = collect_background_controls(
        base, uid, private_root / "background-controls" / "final"
    )
    write_json(sanitized_root / "background-controls-final.json", final_controls)
    inventory_after = collect_package_inventory(
        base, private_root / "inventories" / "final-packages-private.txt"
    )
    added = sorted(set(inventory_after) - set(inventory_before))
    removed = sorted(set(inventory_before) - set(inventory_after))
    write_json(sanitized_root / "package-lineage-check.json", {
        "package_count_before": len(inventory_before),
        "package_count_after": len(inventory_after),
        "added_count": len(added),
        "removed_count": len(removed),
        "added_package_hmacs": [pseudonym(key, "pkg", p) for p in added],
        "removed_package_hmacs": [pseudonym(key, "pkg", p) for p in removed],
        "additional_package_installed": bool(added),
    })
    write_json(
        sanitized_root / "permissions-final.json",
        collect_sanitized_permission_state(
            base, HI_ROKID,
            private_root / "permissions" / "final-dumpsys-private.txt",
        ),
    )

    run_info["end_utc"] = utc_now()
    run_info["phases_completed"] = [
        "A_BACKGROUND_NOT_ENABLED", "BACKGROUND_SETTING_TRANSITION",
        "B_BACKGROUND_ENABLED", "D_FORCE_STOP_CONTROL", "E_RELAUNCH_CONTROL",
    ]
    run_info["machine_visible_background_setting_change"] = diff["changed_count"] > 0
    write_json(sanitized_root / "run-info.json", run_info)

    upload_zip = root.with_name(root.name + "-SANITIZED-UPLOAD.zip")
    packaged = package_sanitized_upload(sanitized_root, upload_zip)
    print("\nTest 16D complete")
    print("=================")
    print(f"Private raw evidence (DO NOT UPLOAD): {private_root}")
    print(f"Sanitized upload ZIP:                 {packaged['zip']}")
    print(f"Sanitized ZIP SHA-256:                {packaged['sha256']}")
    print(f"Privacy gate:                         {packaged['privacy_gate']}")
    print("\nUpload only the -SANITIZED-UPLOAD.zip file.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestAbort as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("\nERROR: interrupted; private evidence was retained.", file=sys.stderr)
        raise SystemExit(130)
