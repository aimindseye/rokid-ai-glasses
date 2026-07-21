# Public Scripts

These interactive tools generate **private evidence**. Their output should be
stored outside the Git worktree.

## Tests

- `tests/run_14a_r2_manual_voice.py`
- `tests/run_14b_firmware_check.py`
- `tests/run_15a_vision_workflow.py`
- `tests/run_15b_visual_routing_retention.py`
- `tests/run_16a_rokid_background_service.py` — legacy private-evidence lifecycle runner
- `tests/run_16b_pixel_clean_install.py` — privacy-first package and first-run runner
- `tests/run_16b_r2_unauthenticated_repair.py` — clean no-login repair
- `tests/run_16c_r2_paired_background.py` — paired data-sharing/lifecycle runner
- `tests/run_16d_pixel_background_ab.py` — background-banner A/B runner
- `tests/test16_common.py` — local sanitizer, HMAC pseudonymization, TLS direction analysis, and privacy gate
- `tests/run_rokid_test17e_visual_ai_interface.sh` — passive half-second visual-AI interface monitor
- `tests/run_rokid_test17f_static_dev_baseline.sh` — read-only glasses OS/package/service baseline with optional private APK pulls
- `tests/check_rokid_adb_state.sh` — read-only USB/wireless ADB state check

## Recovery

- `recovery/audit_recover_14a_r2_evidence.py`
- `recovery/recover_14b_d1_media.py`
- `recovery/finalize_14b_disconnected_d1.py`

## Requirements

- Python 3.10+
- Android platform tools (`adb`)
- authorized Android phone
- for Test 17, one authorized `model:RG_glasses` USB ADB target and the original data/debug cable
- PCAPdroid configured for the controlled app/account where required

Generated evidence can include captures, TLS keys, screenshots, logs,
bugreports, session data, and precise context.


## Test 16 privacy-first output

Test 16B–16D create:

```text
private-raw-DO-NOT-UPLOAD/
sanitized-upload/
```

Upload only the generated file ending in `-SANITIZED-UPLOAD.zip`. The raw tree
may contain PCAPs, SSL key logs, complete package inventories, logcat, Android
state, account/session values, coordinates, images, and audio.

The Test 16 privacy gate rejects raw captures, TLS keys, APKs, media, private
workstation paths, credentials, JWTs, precise coordinates, and other common
sensitive patterns. It retains only interpretable hostnames, path templates,
counts, event types, hashes, and sensitive-field presence/value state.


## Test 17 private output

Test 17 scripts write private data under `~/rokid-nettest/private/` and
sanitized results under `~/rokid-nettest/sanitized/`.

Private output may contain USB/device serials, interface addresses, raw logs,
package and service metadata, APK binaries, signatures, and complete Android
state. Do not run the static collector from inside the Git worktree, and never
commit the private output.

The Test 17 scripts do not enable wireless ADB, contact TCP 8341, reboot, root,
remount, flash, or modify packages/settings.
