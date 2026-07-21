#!/usr/bin/env python3
"""Test 16B-r2 — Pixel clean unauthenticated-state repair.

Clears only Hi Rokid application data, captures the first post-clear launch to
its login screen, performs direction-aware local TLS analysis, and emits only a
sanitized upload ZIP. The glasses remain bound to the S25.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from test16_common import (
    HI_ROKID,
    TestAbort,
    adb_base,
    adb_shell,
    ask_yes_no,
    capture_phase_interactive,
    collect_package_inventory,
    collect_target_runtime_state,
    discover_pixel_serial,
    get_privacy_key,
    package_details,
    package_sanitized_upload,
    prompt_enter,
    pseudonym,
    run,
    sanitize_logcat,
    start_logcat,
    stop_logcat,
    utc_now,
    validate_pixel,
    write_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Clear Hi Rokid app data on Pixel 7 and capture a direction-aware "
            "first-launch/no-login privacy baseline."
        )
    )
    parser.add_argument("--serial")
    parser.add_argument("--observe-minutes", type=float, default=3.0)
    parser.add_argument("--output")
    args = parser.parse_args()

    serial = args.serial or discover_pixel_serial()
    base = adb_base(serial)
    device = validate_pixel(base)
    user_id = device["current_user"]

    root = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path.home() / "rokid-nettest" / "tests" /
        f"16b-r2-pixel-unauthenticated-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    private_root = root / "private-raw-DO-NOT-UPLOAD"
    sanitized_root = root / "sanitized-upload"
    private_root.mkdir(parents=True)
    sanitized_root.mkdir(parents=True)

    key, key_path = get_privacy_key()
    inventory = collect_package_inventory(
        base, private_root / "inventory-before-clear-private.txt"
    )
    if HI_ROKID not in inventory:
        raise TestAbort("Hi Rokid is not installed on the Pixel. Complete Test 16B first.")

    details = package_details(
        base, HI_ROKID, private_root / "hi-rokid-package-before-clear-private.txt"
    )
    uid = inventory[HI_ROKID].get("uid", "") or details.get("uid", "")
    target_uids = {uid} if uid else set()
    target_packages = {HI_ROKID}

    run_info = {
        "schema": "rokid.test16b-r2.sanitized.v1",
        "test_id": "16b-r2-pixel-clean-unauthenticated-repair",
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
            "glasses_remain_bound_to_s25": True,
            "pixel_pairing_permitted": False,
            "rokid_login_permitted": False,
            "optional_permission_grants_permitted": False,
            "hi_rokid_data_clear_required": True,
        },
        "privacy": {
            "private_raw_uploaded": False,
            "direction_aware_tls_analysis": True,
            "sensitive_values_retained_in_upload": False,
            "redaction_key_stored_locally": True,
            "redaction_key_filename": key_path.name,
        },
    }
    write_json(sanitized_root / "run-info.json", run_info)

    prompt_enter(
        "Confirm the glasses are still bound to the S25. Do NOT unbind, pair, restart, "
        "or factory-reset the glasses. Confirm PCAPdroid still has the App decryption "
        "rule for Hi Rokid, TLS decryption enabled, Block QUIC enabled, and App Filter "
        "set to Hi Rokid."
    )

    # Clear only Hi Rokid's app data. The package remains installed and the PCAPdroid
    # rule remains in PCAPdroid's separate app data.
    run([*base, "logcat", "-c"], check=False)
    clear_log_path = private_root / "clear" / "pm-clear-logcat-private.txt"
    clear_log_path.parent.mkdir(parents=True, exist_ok=True)
    clear_log = start_logcat(base, clear_log_path)
    try:
        adb_shell(base, "am", "force-stop", HI_ROKID, check=False)
        clear_result = adb_shell(base, "pm", "clear", HI_ROKID, check=False)
        (private_root / "clear" / "pm-clear-command-private.txt").write_text(
            clear_result.stdout + clear_result.stderr, encoding="utf-8"
        )
        time.sleep(5)
    finally:
        stop_logcat(clear_log)

    clear_success = clear_result.returncode == 0 and "Success" in (
        clear_result.stdout + clear_result.stderr
    )
    if not clear_success:
        raise TestAbort("pm clear did not return Success. See the private clear log.")

    pid_result = adb_shell(base, "pidof", HI_ROKID, check=False)
    services_result = adb_shell(
        base, "dumpsys", "activity", "services", HI_ROKID, check=False
    )
    process_present = bool(pid_result.stdout.strip())
    service_present = bool(re.search(
        rf"ServiceRecord[^\n]*{re.escape(HI_ROKID)}", services_result.stdout
    ))
    collect_target_runtime_state(
        base, private_root / "clear" / "state-after-clear", [HI_ROKID], "after-clear"
    )
    restore_setting = adb_shell(
        base, "settings", "get", "secure", "backup_auto_restore", check=False
    ).stdout.strip()
    write_json(
        sanitized_root / "clear-state.json",
        {
            "pm_clear_success": clear_success,
            "package_remained_installed": True,
            "process_present_after_clear": process_present,
            "active_service_present_after_clear": service_present,
            "android_auto_restore_setting": (
                "enabled" if restore_setting == "1"
                else "disabled" if restore_setting == "0"
                else "unknown"
            ),
            "clear_log_event_summary": sanitize_logcat(clear_log_path),
        },
    )
    if process_present or service_present:
        raise TestAbort(
            "Hi Rokid process/service remained after pm clear. Private evidence retained; "
            "do not proceed until the state is understood."
        )

    duration = max(60, int(args.observe_minutes * 60))
    capture_phase_interactive(
        base,
        user_id,
        "U1",
        private_root / "phases" / "U1-first-launch-after-clear-no-login",
        duration,
        "Launch Hi Rokid from its app icon for the FIRST time after pm clear. Accept only "
        "the minimum terms needed to reach the login/onboarding screen. Do NOT enter or "
        "select an email, password, saved credential, passkey, Google account, or Rokid "
        "account. Do NOT grant optional permissions and do NOT pair the glasses. Return "
        "here when the login/onboarding screen is stable. Confirm at least one Hi Rokid "
        "connection shows the green open-lock icon before stopping the capture.",
        target_packages,
        target_uids,
        require_ssl_keylog=True,
    )

    observations = {
        "login_or_onboarding_screen_reached": ask_yes_no(
            "Did Hi Rokid remain at a login/onboarding screen?", default=True
        ),
        "already_authenticated_without_credentials": ask_yes_no(
            "Did Hi Rokid show a signed-in account/home screen without you entering credentials?"
        ),
        "email_password_or_saved_credential_used": ask_yes_no(
            "Did you enter/select any email, password, saved credential, passkey, or account?"
        ),
        "optional_permission_granted": ask_yes_no(
            "Did you grant any optional permission?"
        ),
        "glasses_pairing_or_transfer_started": ask_yes_no(
            "Did any glasses pairing, binding, unbinding, or account-transfer step start?"
        ),
        "green_open_lock_observed": ask_yes_no(
            "Did at least one Hi Rokid connection show a green open-lock icon?", default=True
        ),
    }
    observations["controlled_phase_valid"] = bool(
        observations["login_or_onboarding_screen_reached"]
        and not observations["email_password_or_saved_credential_used"]
        and not observations["optional_permission_granted"]
        and not observations["glasses_pairing_or_transfer_started"]
        and observations["green_open_lock_observed"]
    )
    write_json(sanitized_root / "operator-observations.json", observations)

    # End in a quiet, unpaired state. This does not affect the S25 binding.
    adb_shell(base, "am", "force-stop", HI_ROKID, check=False)
    run_info["end_utc"] = utc_now()
    run_info["controlled_phase_valid"] = observations["controlled_phase_valid"]
    write_json(sanitized_root / "run-info.json", run_info)

    upload_zip = root.with_name(root.name + "-SANITIZED-UPLOAD.zip")
    result = package_sanitized_upload(sanitized_root, upload_zip)

    print("\nTest 16B-r2 complete")
    print("=====================")
    print(f"Private raw evidence (DO NOT UPLOAD): {private_root}")
    print(f"Sanitized upload ZIP:                 {result['zip']}")
    print(f"Sanitized ZIP SHA-256:                {result['sha256']}")
    print(f"Privacy gate:                         {result['privacy_gate']}")
    print(f"Controlled phase valid:               {observations['controlled_phase_valid']}")
    print("\nKeep the glasses bound to the S25. Upload only the SANITIZED-UPLOAD ZIP.")
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
