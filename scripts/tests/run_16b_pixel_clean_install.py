#!/usr/bin/env python3
"""Test 16B — Pixel clean-install package lineage and first-run data sharing."""

from __future__ import annotations

import argparse
import json
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from test16_common import (
    EXPECTED_APKS_SHA256,
    HI_ROKID,
    TestAbort,
    adb_base,
    adb_shell,
    capture_phase_interactive,
    collect_package_inventory,
    collect_target_runtime_state,
    discover_pixel_serial,
    get_privacy_key,
    hash_remote_file,
    package_details,
    package_sanitized_upload,
    prompt_enter,
    pseudonym,
    run,
    sanitized_package_diff,
    sha256_file,
    start_logcat,
    stop_logcat,
    utc_now,
    validate_pixel,
    write_json,
)


def install_apks(base, apks_path: Path, private_root: Path) -> None:
    if sha256_file(apks_path) != EXPECTED_APKS_SHA256:
        raise TestAbort(
            "APKS SHA-256 mismatch. Expected the reviewed rokid_app.apks artifact."
        )
    extract_dir = private_root / "installation" / "extracted-apks-private"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apks_path) as archive:
        archive.extractall(extract_dir)
    apks = sorted(extract_dir.glob("*.apk"))
    expected = {
        "base.apk",
        "split_config.arm64_v8a.apk",
        "split_config.xxhdpi.apk",
        "split_install_time_asset_pack.apk",
    }
    if {p.name for p in apks} != expected:
        raise TestAbort(f"Unexpected APKS contents: {[p.name for p in apks]}")
    result = run([*base, "install-multiple", "-r", *map(str, apks)], check=False)
    (private_root / "installation" / "adb-install-private.txt").write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    if result.returncode != 0 or "Success" not in result.stdout + result.stderr:
        raise TestAbort("adb install-multiple failed. See private install log.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Privacy-first Pixel clean-install and first-run test for Hi Rokid."
    )
    parser.add_argument("--serial")
    parser.add_argument(
        "--apks",
        default=str(Path.home() / "Downloads" / "rokid_app.apks"),
        help="Exact reviewed rokid_app.apks artifact.",
    )
    parser.add_argument("--observe-minutes", type=float, default=3.0)
    parser.add_argument("--output")
    args = parser.parse_args()

    serial = args.serial or discover_pixel_serial()
    base = adb_base(serial)
    device = validate_pixel(base)
    user_id = device["current_user"]
    apks_path = Path(args.apks).expanduser().resolve()
    if not apks_path.is_file():
        raise TestAbort(f"APKS not found: {apks_path}")

    root = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path.home() / "rokid-nettest" / "tests" /
        f"16b-pixel-clean-install-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    private_root = root / "private-raw-DO-NOT-UPLOAD"
    sanitized_root = root / "sanitized-upload"
    private_root.mkdir(parents=True)
    sanitized_root.mkdir(parents=True)

    key, key_path = get_privacy_key()
    run_info = {
        "schema": "rokid.test16b.sanitized.v1",
        "test_id": "16b-pixel-clean-install-lineage-first-run",
        "start_utc": utc_now(),
        "phone": {
            "model": device["model"],
            "android_release": device["android_release"],
            "sdk": device["sdk"],
            "device_serial_hmac": pseudonym(key, "device", device["serial"]),
        },
        "apks_sha256": sha256_file(apks_path),
        "privacy": {
            "private_raw_uploaded": False,
            "redaction_key_stored_locally": True,
            "redaction_key_filename": key_path.name,
        },
    }
    write_json(sanitized_root / "run-info.json", run_info)

    # P0 — preinstall.
    before = collect_package_inventory(
        base, private_root / "inventories" / "P0-preinstall-packages-private.txt"
    )
    if HI_ROKID in before:
        raise TestAbort(
            "Hi Rokid is already installed on the Pixel. Uninstall it and rerun."
        )
    restore_setting = adb_shell(
        base, "settings", "get", "secure", "backup_auto_restore", check=False
    ).stdout.strip()
    write_json(
        sanitized_root / "P0-preinstall.json",
        {
            "hi_rokid_installed": False,
            "package_count": len(before),
            "package_hmacs": sorted(pseudonym(key, "pkg", pkg) for pkg in before),
            "android_auto_restore_setting": (
                "enabled" if restore_setting == "1"
                else "disabled" if restore_setting == "0"
                else "unknown"
            ),
        },
    )

    if restore_setting == "1":
        prompt_enter(
            "Android Automatic restore appears ENABLED. For the cleanest test, temporarily "
            "disable app-data restore in Pixel backup settings, then return. The script will "
            "also record any restore-at-install activity in logcat."
        )

    prompt_enter(
        "P0 baseline complete. Confirm the glasses remain bound to the S25. "
        "Do not unbind or pair them with the Pixel yet. After installation and before "
        "P2 capture, configure PCAPdroid > Decryption rules > Add > App > Hi Rokid. "
        "Enable TLS decryption and Block QUIC. Do not use a country-only rule."
    )

    # Install under logcat to detect restore-at-install.
    run([*base, "logcat", "-c"], check=False)
    install_log = start_logcat(
        base, private_root / "installation" / "install-logcat-private.txt"
    )
    try:
        install_apks(base, apks_path, private_root)
        time.sleep(8)
    finally:
        stop_logcat(install_log)

    after = collect_package_inventory(
        base, private_root / "inventories" / "P1-postinstall-packages-private.txt"
    )
    details = package_details(
        base, HI_ROKID, private_root / "installation" / "hi-rokid-dumpsys-private.txt"
    )
    if HI_ROKID not in after:
        raise TestAbort("Hi Rokid was not present after installation.")

    diff = sanitized_package_diff(key, before, after, {HI_ROKID})
    remote_hashes = [hash_remote_file(base, path) for path in details["paths"]]
    p1 = {
        "phase": "P1-installed-never-launched",
        "package_diff": diff,
        "hi_rokid": {
            "package": HI_ROKID,
            "version_name": details["version_name"],
            "version_code": details["version_code"],
            "installer": details["installer"],
            "installed_splits": remote_hashes,
        },
        "additional_package_installed": any(
            item["package"] != HI_ROKID for item in diff["added"]
        ),
    }
    write_json(sanitized_root / "P1-installed-never-launched.json", p1)

    target_packages = {item["package"] for item in diff["added"] if item["package"]}
    target_packages.add(HI_ROKID)
    target_uids = {
        after[pkg]["uid"] for pkg in target_packages
        if pkg in after and after[pkg].get("uid")
    }

    # P2 — first launch, no login.
    duration = max(60, int(args.observe_minutes * 60))
    capture_phase_interactive(
        base, user_id, "P2", private_root / "phases" / "P2-first-launch-no-login",
        duration,
        "Launch Hi Rokid from the app icon. Accept only the minimum terms required to reach "
        "the login screen. Do NOT log in, grant optional permissions, or pair glasses. "
        "Return here when the login/onboarding screen is stable.",
        target_packages, target_uids, require_ssl_keylog=True,
    )

    # P3 — same account login, no pairing.
    capture_phase_interactive(
        base, user_id, "P3", private_root / "phases" / "P3-login-no-pairing",
        duration,
        "Open Hi Rokid and sign in using the SAME Rokid account used on the S25. "
        "Do NOT accept a glasses transfer, unbind, or pair. Grant no optional permissions "
        "unless login cannot continue without them. Return here after the signed-in, "
        "not-paired screen is stable.",
        target_packages, target_uids, require_ssl_keylog=True,
    )

    # Re-snapshot packages to detect delayed companion installs.
    final_inventory = collect_package_inventory(
        base, private_root / "inventories" / "P3-final-packages-private.txt"
    )
    delayed_diff = sanitized_package_diff(key, after, final_inventory, {HI_ROKID})
    write_json(
        sanitized_root / "P3-delayed-package-diff.json",
        {
            "phase": "after-first-launch-and-login",
            "package_diff": delayed_diff,
            "delayed_additional_package_installed": delayed_diff["added_count"] > 0,
        },
    )

    run_info["end_utc"] = utc_now()
    run_info["target_packages"] = sorted(target_packages)
    run_info["target_uid_hmacs"] = sorted(
        pseudonym(key, "uid", uid) for uid in target_uids
    )
    write_json(sanitized_root / "run-info.json", run_info)

    upload_zip = root.with_name(root.name + "-SANITIZED-UPLOAD.zip")
    result = package_sanitized_upload(sanitized_root, upload_zip)

    print("\nTest 16B complete")
    print("=================")
    print(f"Private raw evidence (DO NOT UPLOAD): {private_root}")
    print(f"Sanitized upload ZIP:                 {result['zip']}")
    print(f"Sanitized ZIP SHA-256:                {result['sha256']}")
    print(f"Privacy gate:                         {result['privacy_gate']}")
    print("\nKeep the glasses bound to the S25 until this sanitized ZIP is reviewed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestAbort as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("\nERROR: interrupted.", file=sys.stderr)
        raise SystemExit(130)
