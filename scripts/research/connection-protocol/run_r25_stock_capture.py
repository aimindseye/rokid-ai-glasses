#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from r25lib import adb, manifest, require_command, sanitize_text, write_json

STOCK_PACKAGE = "com.rokid.sprite.global.aiapp"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Capture synchronized stock pairing and Developer Mode evidence.")
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--phone-serial")
    result.add_argument("--glasses-serial")
    result.add_argument("--phase-set", choices=["pairing", "developer-mode", "both"], default="both")
    result.add_argument("--collect-bugreport", action="store_true")
    result.add_argument("--allow-developer-toggle", action="store_true")
    result.add_argument("--non-interactive", action="store_true", help="Synthetic/automation mode only; do not use for a live stock action.")
    return result


def list_devices() -> list[str]:
    completed = subprocess.run(["adb", "devices"], check=True, capture_output=True, text=True)
    devices: list[str] = []
    for line in completed.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and fields[1] == "device":
            devices.append(fields[0])
    return devices


def prop(serial: str, key: str) -> str:
    return adb(serial, "shell", "getprop", key, check=False).stdout.strip()


def auto_select(phone: str | None, glasses: str | None) -> tuple[str, str | None]:
    devices = list_devices()
    models = {item: prop(item, "ro.product.model") for item in devices}
    if glasses is None:
        candidates = [serial for serial, model in models.items() if "RG-glasses" in model or model.lower() == "rg-glasses"]
        if len(candidates) == 1:
            glasses = candidates[0]
    if phone is None:
        candidates = [serial for serial in devices if serial != glasses]
        package_matches = [serial for serial in candidates if adb(serial, "shell", "pm", "path", STOCK_PACKAGE, check=False).returncode == 0]
        if len(package_matches) == 1:
            phone = package_matches[0]
        elif len(candidates) == 1:
            phone = candidates[0]
    if phone is None:
        raise SystemExit(f"unable to select phone from ADB devices: {models}; pass --phone-serial")
    if glasses is not None and glasses == phone:
        raise SystemExit("phone and glasses serials resolve to the same device")
    return phone, glasses


def prompt(text: str, non_interactive: bool) -> None:
    print("\n=== OPERATOR ACTION ===")
    print(text)
    if non_interactive:
        print("R25_NON_INTERACTIVE_AUTO_CONTINUE=YES")
        return
    input("Press Enter after completing the action... ")


def append_timeline(path: Path, phase: str, event: str, note: str = "") -> None:
    row = {
        "schema": "rokid.r25.timeline-event.v1",
        "time_epoch_ns": time.time_ns(),
        "phase": phase,
        "event": event,
        "note": note,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def save_command(path: Path, command: list[str], *, timeout: int = 90) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    text = completed.stdout
    if completed.stderr:
        text += "\n--- STDERR ---\n" + completed.stderr
    path.write_text(text, encoding="utf-8")
    return completed.returncode


def phone_snapshot(phone: str, out: Path, phase: str) -> None:
    phase_dir = out / "snapshots" / phase / "phone"
    save_command(phase_dir / "bluetooth-manager-private.txt", ["adb", "-s", phone, "shell", "dumpsys", "bluetooth_manager"])
    save_command(phase_dir / "package-private.txt", ["adb", "-s", phone, "shell", "dumpsys", "package", STOCK_PACKAGE])
    save_command(phase_dir / "services-private.txt", ["adb", "-s", phone, "shell", "dumpsys", "activity", "services", STOCK_PACKAGE])
    save_command(phase_dir / "activity-private.txt", ["adb", "-s", phone, "shell", "dumpsys", "activity", "activities", STOCK_PACKAGE])


def glasses_snapshot(glasses: str | None, out: Path, phase: str) -> None:
    phase_dir = out / "snapshots" / phase / "glasses"
    phase_dir.mkdir(parents=True, exist_ok=True)
    if glasses is None:
        write_json(phase_dir / "adb-state-private.json", {
            "schema": "rokid.r25.glasses-adb-state.v1",
            "reachable": False,
            "reason": "glasses ADB serial unavailable",
        })
        return
    fields = {
        "reachable": True,
        "model": prop(glasses, "ro.product.model"),
        "persist_vendor_adb": prop(glasses, "persist.vendor.adb"),
        "persist_sys_usb_config": prop(glasses, "persist.sys.usb.config"),
        "sys_usb_config": prop(glasses, "sys.usb.config"),
        "adb_enabled": adb(glasses, "shell", "settings", "get", "global", "adb_enabled", check=False).stdout.strip(),
        "adb_wifi_enabled": adb(glasses, "shell", "settings", "get", "global", "adb_wifi_enabled", check=False).stdout.strip(),
    }
    write_json(phase_dir / "adb-state-private.json", {"schema": "rokid.r25.glasses-adb-state.v1", **fields})


def snapshot(phone: str, glasses: str | None, out: Path, phase: str, timeline: Path) -> None:
    append_timeline(timeline, phase, "snapshot_start")
    phone_snapshot(phone, out, phase)
    glasses_snapshot(glasses, out, phase)
    append_timeline(timeline, phase, "snapshot_complete")


def main() -> int:
    args = parser().parse_args()
    require_command("adb")
    out = args.output.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    timeline = out / "timeline-private.ndjson"
    if timeline.exists():
        timeline.unlink()

    phone, glasses = auto_select(args.phone_serial, args.glasses_serial)
    metadata = {
        "schema": "rokid.r25.capture-metadata.v1",
        "start_epoch_ns": time.time_ns(),
        "stock_package": STOCK_PACKAGE,
        "phone_serial_private": phone,
        "glasses_serial_private": glasses,
        "phase_set": args.phase_set,
        "collect_bugreport": args.collect_bugreport,
        "allow_developer_toggle": args.allow_developer_toggle,
        "automatic_device_write": False,
    }
    write_json(out / "capture-metadata-private.json", metadata)

    logcat_path = out / "phone-logcat-private.txt"
    log_handle = logcat_path.open("w", encoding="utf-8")
    logcat = subprocess.Popen(
        ["adb", "-s", phone, "logcat", "-v", "epoch", "*:V"],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    append_timeline(timeline, "capture", "logcat_started")

    try:
        snapshot(phone, glasses, out, "baseline", timeline)
        prompt("Open Hi Rokid and leave it idle for at least 10 seconds. Do not pair, reconnect, or toggle settings.", args.non_interactive)
        snapshot(phone, glasses, out, "stock_idle", timeline)

        if args.phase_set in {"pairing", "both"}:
            append_timeline(timeline, "pairing_or_reconnect", "operator_action_start")
            prompt("Perform exactly one stock glasses connect, reconnect, or pairing action. Avoid other Bluetooth actions.", args.non_interactive)
            append_timeline(timeline, "pairing_or_reconnect", "operator_action_complete")
            snapshot(phone, glasses, out, "pairing_or_reconnect", timeline)

        if args.phase_set in {"developer-mode", "both"}:
            append_timeline(timeline, "developer_mode_view", "operator_action_start")
            prompt("Open the stock Developer Mode screen and observe the current state. Do not toggle it.", args.non_interactive)
            append_timeline(timeline, "developer_mode_view", "operator_action_complete")
            snapshot(phone, glasses, out, "developer_mode_view", timeline)

            if args.allow_developer_toggle:
                if not args.non_interactive:
                    phrase = input("Type exactly 'ADB MAY DISCONNECT' to permit manual stock toggles: ")
                    if phrase != "ADB MAY DISCONNECT":
                        raise SystemExit("developer toggle confirmation did not match")
                append_timeline(timeline, "developer_mode_off", "operator_action_start")
                prompt("Using only the stock Hi Rokid UI, toggle Developer Mode OFF. Do not issue ADB property commands.", args.non_interactive)
                append_timeline(timeline, "developer_mode_off", "operator_action_complete")
                time.sleep(2)
                snapshot(phone, glasses, out, "developer_mode_off", timeline)

                append_timeline(timeline, "developer_mode_on", "operator_action_start")
                prompt("Using only the stock Hi Rokid UI, toggle Developer Mode ON and wait for a positive UI result.", args.non_interactive)
                append_timeline(timeline, "developer_mode_on", "operator_action_complete")
                time.sleep(2)
                snapshot(phone, glasses, out, "developer_mode_on", timeline)
    finally:
        append_timeline(timeline, "capture", "logcat_stop_requested")
        logcat.send_signal(signal.SIGINT)
        try:
            logcat.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logcat.terminate()
            logcat.wait(timeout=5)
        log_handle.close()

    if args.collect_bugreport:
        bugreport = out / "phone-bugreport-private.zip"
        print("R25_BUGREPORT_CAPTURE=START")
        completed = subprocess.run(["adb", "-s", phone, "bugreport", str(bugreport)], text=True)
        print(f"R25_BUGREPORT_CAPTURE_RC={completed.returncode}")

    rows = manifest(out, out / "SHA256SUMS-private.json", exclude=[out / "SHA256SUMS-private.json"])
    print(f"R25_CAPTURE_FILE_COUNT={len(rows)}")
    print(f"R25_PHONE_SELECTED=YES")
    print(f"R25_GLASSES_ADB_SELECTED={'YES' if glasses else 'NO'}")
    print(f"R25_STOCK_CAPTURE={out}")
    print("R1_3_3_2_25_STOCK_CAPTURE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
