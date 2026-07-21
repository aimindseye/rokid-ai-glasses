# Public Evidence

Only reviewed and sanitized evidence is stored here.

Excluded:

- raw captures and TLS keys;
- decrypted payload dumps;
- logcat, bugreports, and HCI logs;
- credentials and device/account identifiers;
- APKs and native libraries.

Test 14 publication:

- `sanitized/14a/`
- `sanitized/14a-r2/`
- `sanitized/14b/`
- `sanitized/15/` — consolidated visual AI architecture summary
- `sanitized/16/` — Android background service, package lineage, and data-sharing summary
- `sanitized/17/` — glasses Android/ADB/boot/service/network assertions
- `manifests/` hash-only provenance


Test 17 additionally excludes ADB host keys, authorized-host files, USB/device
serials, raw package/Binder/HAL/process dumps, selected vendor APK binaries,
complete block-device maps, and all partition images. Public package
provenance is hash-only.
