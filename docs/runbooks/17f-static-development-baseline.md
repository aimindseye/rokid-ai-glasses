# Runbook 17F — Static Development Baseline

## Purpose

Preserve a read-only development and provenance baseline while USB ADB is
available.

## Run

```bash
cd /path/to/rokid-ai-glasses
chmod +x scripts/tests/run_rokid_test17f_static_dev_baseline.sh
./scripts/tests/run_rokid_test17f_static_dev_baseline.sh
```

The collector selects exactly one connected `model:RG_glasses` target and
creates separate private and sanitized directories under `~/rokid-nettest`.

To skip private APK pulls:

```bash
PULL_SELECTED_APKS=0 \
  ./scripts/tests/run_rokid_test17f_static_dev_baseline.sh
```

## Collection scope

- build, kernel, ADB, USB, and verified-boot properties;
- package, permission, Binder, HAL, and system-service inventories;
- camera, audio, input, display, sensor, Bluetooth, network, and listener state;
- GateServiced process/init metadata;
- selected vendor-package versions, paths, and SHA-256 hashes;
- optional private APK pulls with host/device hash comparison.

## Exclusions

The collector does not:

- reboot, root, remount, flash, or alter verified boot;
- enable wireless ADB;
- install, uninstall, enable, disable, or force-stop packages;
- connect to TCP 8341;
- extract any Android partition image.

## Public/private boundary

Only the generated sanitized assertions, summary, and hash manifest are
candidates for publication. Private APKs, raw dumps, logs, addresses, serials,
USB metadata, package dumps, and decompilation output remain outside Git.

## Accepted result

```text
SANITIZED_PRIVACY_GATE=PASS
SELECTED_VENDOR_PACKAGES_PRESENT=8_OF_8
PRIVATE_APKS_PULLED=8_OF_8
HOST_DEVICE_APK_HASH_MATCH=8_OF_8
```
