#!/usr/bin/env python3
"""Test 16C-r2 — direction-aware Pixel pairing and background lifecycle test.

The login itself occurs with PCAPdroid stopped so the test does not retain a
second copy of the user's password. Captured phases begin after login and cover
unpaired bootstrap, controlled S25-to-Pixel binding transfer, paired idle,
voice/visual AI, Recents dismissal, force-stop, screen-off, and relaunch.

Raw PCAPs, TLS keys, logcat, device identifiers, account data, coordinates,
images, audio, and tokens remain only in private local evidence. Only a
privacy-gated sanitized ZIP is intended for upload.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List

from test16_common import (
    HI_ROKID,
    TestAbort,
    adb_base,
    adb_shell,
    ask_yes_no,
    capture_phase_interactive,
    collect_package_inventory,
    collect_sanitized_permission_state,
    discover_pixel_serial,
    get_privacy_key,
    package_details,
    package_sanitized_upload,
    prompt_enter,
    pseudonym,
    sanitized_package_diff,
    utc_now,
    validate_pixel,
    write_json,
)


def shell_cmd(base: List[str], *args: str) -> List[str]:
    return [*base, "shell", *args]


def force_stop_and_launch_commands(base: List[str]) -> List[List[str]]:
    return [
        shell_cmd(base, "am", "force-stop", HI_ROKID),
        shell_cmd(
            base, "monkey", "-p", HI_ROKID,
            "-c", "android.intent.category.LAUNCHER", "1",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Privacy-first, direction-aware Pixel 7 pairing, AI, foreground-service, "
            "Recents, force-stop, screen-off, and relaunch test."
        )
    )
    parser.add_argument("--serial")
    parser.add_argument("--observe-minutes", type=float, default=3.0)
    parser.add_argument("--control-minutes", type=float, default=2.0)
    parser.add_argument("--snapshot-seconds", type=int, default=20)
    parser.add_argument("--skip-visual", action="store_true")
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
        f"16c-r2-pixel-paired-background-{time.strftime('%Y%m%d-%H%M%S')}"
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
        raise TestAbort("Hi Rokid is not installed on the Pixel. Complete Test 16B first.")

    details = package_details(
        base, HI_ROKID, private_root / "inventories" / "hi-rokid-start-private.txt"
    )
    uid = inventory_before[HI_ROKID].get("uid", "") or details.get("uid", "")
    target_packages = {HI_ROKID}
    target_uids = {uid} if uid else set()

    observe = max(60, int(args.observe_minutes * 60))
    control = max(60, int(args.control_minutes * 60))
    snapshots = max(10, int(args.snapshot_seconds))
    full_exports = {"pcap", "ssl_keylog", "sidecar"}

    run_info: Dict[str, object] = {
        "schema": "rokid.test16c-r2.sanitized.v1",
        "test_id": "16c-r2-pixel-pairing-ai-background-lifecycle",
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
            "same_rokid_account_as_s25_required": True,
            "login_credentials_captured_in_this_test": False,
            "glasses_restart_or_power_cycle_permitted": False,
            "glasses_factory_reset_permitted": False,
            "unbind_s25_only_during_pairing_phase": True,
            "pcapdroid_app_filter": HI_ROKID,
            "tls_decryption_required": True,
            "block_quic_controlled_run": True,
            "direction_aware_analysis": True,
            "snapshot_seconds": snapshots,
        },
        "privacy": {
            "private_raw_uploaded": False,
            "sensitive_values_retained_in_upload": False,
            "redaction_key_stored_locally": True,
            "redaction_key_filename": key_path.name,
        },
    }
    write_json(sanitized_root / "run-info.json", run_info)

    prompt_enter(
        "PREPARATION: Keep the glasses bound to the S25. Do NOT unbind, restart, "
        "power-cycle, or factory-reset them. Confirm PCAPdroid has App Filter = Hi Rokid, "
        "App decryption rule = Hi Rokid, TLS decryption enabled, Block QUIC enabled, and "
        "dump mode = PCAP file. PCAPdroid must NOT be recording during the login step."
    )

    # Login outside packet capture to avoid retaining another copy of the password.
    adb_shell(base, "am", "force-stop", HI_ROKID, check=False)
    adb_shell(
        base, "monkey", "-p", HI_ROKID,
        "-c", "android.intent.category.LAUNCHER", "1", check=False,
    )
    prompt_enter(
        "With PCAPdroid stopped, sign in to Hi Rokid using the SAME Rokid account used on "
        "the S25. Do NOT pair or transfer the glasses yet. Do not grant Contacts, Calendar, "
        "Notification access, media, or background location unless the app absolutely "
        "requires it to finish login. Return when the signed-in unpaired home screen is stable."
    )
    login_observations = {
        "same_account_as_s25_used": ask_yes_no(
            "Did you use the same Rokid account as the S25?", default=True
        ),
        "pixel_still_unpaired": ask_yes_no(
            "Are the glasses still bound to the S25 and unpaired from the Pixel?", default=True
        ),
        "pcapdroid_stopped_during_login": ask_yes_no(
            "Was PCAPdroid stopped for the entire login step?", default=True
        ),
    }
    if not all(login_observations.values()):
        raise TestAbort("Login preparation controls were not satisfied. Do not transfer pairing.")
    adb_shell(base, "am", "force-stop", HI_ROKID, check=False)
    write_json(sanitized_root / "login-preparation-controls.json", login_observations)
    write_json(
        sanitized_root / "permissions-prepairing.json",
        collect_sanitized_permission_state(
            base, HI_ROKID,
            private_root / "permissions" / "prepairing-dumpsys-private.txt",
        ),
    )

    observations: Dict[str, object] = {}

    # C0: logged-in, unpaired bootstrap after a force-stop/relaunch.
    capture_phase_interactive(
        base, user_id, "C0",
        private_root / "phases" / "C0-logged-in-unpaired-relaunch",
        observe,
        "Hi Rokid has been relaunched after PCAPdroid started. Confirm the account is "
        "signed in, the Pixel is still unpaired, and no pairing/transfer prompt was accepted. "
        "Wait until at least one Hi Rokid connection shows a green open-lock icon, then return.",
        target_packages, target_uids,
        required_export_kinds=full_exports,
        snapshot_seconds=snapshots,
        pre_action_commands=force_stop_and_launch_commands(base),
    )
    observations["C0_logged_in_unpaired"] = ask_yes_no(
        "C0: Did the Pixel remain logged in but unpaired?", default=True
    )

    # C1: controlled transfer from S25 to Pixel. No restart/reset.
    capture_phase_interactive(
        base, user_id, "C1",
        private_root / "phases" / "C1-unbind-s25-bind-pixel",
        observe,
        "PAIRING TRANSFER: First confirm the S25 currently shows the glasses connected. "
        "Then unbind the glasses from the S25 through Hi Rokid and bind/pair them to this "
        "Pixel using the SAME Rokid account. Do NOT restart, power-cycle, or factory-reset "
        "the glasses. If an account-mismatch or erase-data warning appears, do not approve it; "
        "abort the script. Return only after the Pixel shows a stable live connection and "
        "battery information, with a green open-lock connection visible in PCAPdroid.",
        target_packages, target_uids,
        required_export_kinds=full_exports,
        snapshot_seconds=snapshots,
        pre_action_commands=force_stop_and_launch_commands(base),
    )
    observations["C1"] = {
        "s25_unbind_completed": ask_yes_no("C1: Did unbinding from the S25 complete?", default=True),
        "pixel_binding_completed": ask_yes_no("C1: Did Pixel binding complete?", default=True),
        "live_battery_visible": ask_yes_no("C1: Did the Pixel show live battery information?", default=True),
        "glasses_restart_or_power_cycle_performed": ask_yes_no(
            "C1: Was any glasses restart or power-cycle performed?"
        ),
        "factory_reset_performed": ask_yes_no("C1: Was any factory reset performed?"),
        "erase_or_account_mismatch_warning_approved": ask_yes_no(
            "C1: Was any erase-data or account-mismatch warning approved?"
        ),
    }
    c1 = observations["C1"]
    assert isinstance(c1, dict)
    if (
        not c1["s25_unbind_completed"]
        or not c1["pixel_binding_completed"]
        or not c1["live_battery_visible"]
        or c1["glasses_restart_or_power_cycle_performed"]
        or c1["factory_reset_performed"]
        or c1["erase_or_account_mismatch_warning_approved"]
    ):
        raise TestAbort("Pairing controls did not pass. Private evidence retained; stop here.")
    write_json(
        sanitized_root / "permissions-postpairing.json",
        collect_sanitized_permission_state(
            base, HI_ROKID,
            private_root / "permissions" / "postpairing-dumpsys-private.txt",
        ),
    )

    # C2: paired idle bootstrap, no AI.
    capture_phase_interactive(
        base, user_id, "C2",
        private_root / "phases" / "C2-paired-idle-relaunch",
        observe,
        "Wait for Hi Rokid to show the glasses connected with live battery information. "
        "Do not invoke voice AI, visual AI, translation, navigation, notification mirroring, "
        "gallery sync, media transfer, or support-log upload. Confirm a green open lock, then return.",
        target_packages, target_uids,
        required_export_kinds=full_exports,
        snapshot_seconds=snapshots,
        pre_action_commands=force_stop_and_launch_commands(base),
    )
    observations["C2_paired_idle_live_battery"] = ask_yes_no(
        "C2: Did connected status and live battery return after relaunch?", default=True
    )

    # C3: one standardized non-sensitive voice request.
    capture_phase_interactive(
        base, user_id, "C3",
        private_root / "phases" / "C3-one-voice-ai-request",
        observe,
        "Wait for connected status, then perform exactly one ordinary voice AI request: "
        "'What color is the sky on a clear day?' Do not include names, addresses, account "
        "details, or other personal information. Wait for the complete answer and confirm a "
        "green open-lock connection before returning.",
        target_packages, target_uids,
        required_export_kinds=full_exports,
        snapshot_seconds=snapshots,
        pre_action_commands=force_stop_and_launch_commands(base),
    )
    observations["C3_voice_request_completed"] = ask_yes_no(
        "C3: Did the one voice request receive a complete response?", default=True
    )

    # C4: one non-sensitive visual request.
    if not args.skip_visual:
        capture_phase_interactive(
            base, user_id, "C4",
            private_root / "phases" / "C4-one-visual-ai-request",
            observe,
            "Display a non-sensitive test image on the iPad containing only simple shapes/colors. "
            "Wait for connected status, then perform exactly one visual request: 'Describe the "
            "shapes and colors you see.' Wait for the response and conversation thumbnail. "
            "Confirm a green open-lock connection before returning.",
            target_packages, target_uids,
            required_export_kinds=full_exports,
            snapshot_seconds=snapshots,
            pre_action_commands=force_stop_and_launch_commands(base),
        )
        observations["C4"] = {
            "visual_request_completed": ask_yes_no(
                "C4: Did the one visual request receive a complete response?", default=True
            ),
            "conversation_thumbnail_visible": ask_yes_no(
                "C4: Was a new conversation thumbnail visible?", default=True
            ),
        }

    # C5: fresh relaunch followed by Recents dismissal, preserving foreground service.
    capture_phase_interactive(
        base, user_id, "C5",
        private_root / "phases" / "C5-recents-dismissed-background",
        observe,
        "Wait for Hi Rokid to show connected status and live battery. Open Android Recents and "
        "swipe Hi Rokid away. Do NOT force-stop it. Confirm the task is absent from Recents; "
        "check whether the Hi Rokid 'AI Service' foreground notification remains, then return.",
        target_packages, target_uids,
        required_export_kinds=full_exports,
        snapshot_seconds=snapshots,
        pre_action_commands=force_stop_and_launch_commands(base),
    )
    observations["C5"] = {
        "recents_task_removed": ask_yes_no("C5: Was Hi Rokid removed from Recents?", default=True),
        "ai_service_notification_remained": ask_yes_no(
            "C5: Did the Hi Rokid AI Service notification remain?", default=True
        ),
        "glasses_still_connected_or_status_available": ask_yes_no(
            "C5: Did the glasses remain connected or continue reporting status?", default=True
        ),
    }

    # C6: capture the force-stop boundary, then screen-on silence.
    capture_phase_interactive(
        base, user_id, "C6",
        private_root / "phases" / "C6-force-stop-screen-on",
        observe,
        "Confirm the AI Service notification is still present from C5. Press Enter; the script "
        "will force-stop Hi Rokid after this prompt. Do not reopen it during the timer.",
        target_packages, target_uids,
        snapshot_seconds=snapshots,
        post_action_commands=[shell_cmd(base, "am", "force-stop", HI_ROKID)],
    )
    observations["C6"] = {
        "ai_service_notification_gone": ask_yes_no(
            "C6: Did the AI Service notification disappear after force-stop?", default=True
        ),
        "hi_rokid_remained_closed": ask_yes_no(
            "C6: Did Hi Rokid remain closed for the full phase?", default=True
        ),
    }

    # C7: repeat force-stop and observe with phone screen off. Zero-traffic is valid.
    capture_phase_interactive(
        base, user_id, "C7",
        private_root / "phases" / "C7-force-stop-screen-off",
        observe,
        "Hi Rokid should remain closed. Press Enter; the script will force-stop it again before "
        "the screen-off timer. Do not reopen Hi Rokid.",
        target_packages, target_uids,
        screen_off=True,
        snapshot_seconds=snapshots,
        post_action_commands=[shell_cmd(base, "am", "force-stop", HI_ROKID)],
    )
    observations["C7_hi_rokid_remained_closed"] = ask_yes_no(
        "C7: After unlocking, was Hi Rokid still closed with no AI Service notification?",
        default=True,
    )

    # C8: positive control. Launch only after capture starts.
    capture_phase_interactive(
        base, user_id, "C8",
        private_root / "phases" / "C8-relaunch-reconnect-control",
        control,
        "The script has launched Hi Rokid after PCAPdroid started. Observe the initial UI. "
        "Note whether a transient 'not connected' popup appears, whether the AI Service "
        "notification starts, and whether connected status/live battery subsequently return. "
        "Confirm a green open-lock connection, then return.",
        target_packages, target_uids,
        required_export_kinds=full_exports,
        snapshot_seconds=snapshots,
        pre_action_commands=[
            shell_cmd(
                base, "monkey", "-p", HI_ROKID,
                "-c", "android.intent.category.LAUNCHER", "1",
            )
        ],
    )
    observations["C8"] = {
        "transient_not_connected_popup": ask_yes_no(
            "C8: Did a transient 'not connected' popup appear?"
        ),
        "ai_service_notification_started": ask_yes_no(
            "C8: Did the AI Service notification start?", default=True
        ),
        "glasses_reconnected": ask_yes_no("C8: Did the glasses reconnect?", default=True),
        "live_battery_returned": ask_yes_no("C8: Did live battery information return?", default=True),
    }

    write_json(sanitized_root / "operator-observations.json", observations)
    write_json(
        sanitized_root / "permissions-final.json",
        collect_sanitized_permission_state(
            base, HI_ROKID,
            private_root / "permissions" / "final-dumpsys-private.txt",
        ),
    )

    inventory_after = collect_package_inventory(
        base, private_root / "inventories" / "final-packages-private.txt"
    )
    package_diff = sanitized_package_diff(
        key, inventory_before, inventory_after, {HI_ROKID}
    )
    write_json(
        sanitized_root / "package-lineage-after-pairing-ai.json",
        {
            "package_diff": package_diff,
            "additional_package_installed_during_test": package_diff["added_count"] > 0,
        },
    )

    run_info["end_utc"] = utc_now()
    run_info["phases_completed"] = [
        "C0", "C1", "C2", "C3",
        *([] if args.skip_visual else ["C4"]),
        "C5", "C6", "C7", "C8",
    ]
    write_json(sanitized_root / "run-info.json", run_info)

    upload_zip = root.with_name(root.name + "-SANITIZED-UPLOAD.zip")
    result = package_sanitized_upload(sanitized_root, upload_zip)

    print("\nTest 16C-r2 complete")
    print("=====================")
    print(f"Private raw evidence (DO NOT UPLOAD): {private_root}")
    print(f"Sanitized upload ZIP:                 {result['zip']}")
    print(f"Sanitized ZIP SHA-256:                {result['sha256']}")
    print(f"Privacy gate:                         {result['privacy_gate']}")
    print("\nUpload only the -SANITIZED-UPLOAD.zip file.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TestAbort as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("\nERROR: interrupted. Private evidence was retained.", file=sys.stderr)
        raise SystemExit(130)
