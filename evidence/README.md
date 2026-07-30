# Public Evidence

Only reviewed and sanitized summaries or hash-only provenance are stored here.
Raw captures and private application/device evidence remain outside the Git
worktree.

## Index

- [Sanitized evidence index](sanitized/README.md)
- [Manifest index](manifests/README.md)
- [Evidence-handling methodology](../docs/methodology/evidence-handling.md)
- [Test and research matrix](../docs/tests/test-matrix.md)

## Published numbered-test summaries

- `sanitized/03b/` — idle/model-menu traffic summaries
- `sanitized/04/` — model-selection summary
- `sanitized/06c/` — device-connection summary
- `sanitized/10/` — translation series
- `sanitized/14a/` and `sanitized/14a-r2/` — assistant routing
- `sanitized/14b/` — firmware check
- `sanitized/15/` — visual AI
- `sanitized/16/` — background services and privacy
- `sanitized/17/` — glasses Android, ADB, local service, and network assertions
- `sanitized/glasses-os-services/` — Test 18 USB ADB control summary
- `sanitized/ota-firmware/` — OTA/firmware summary
- `sanitized/boot-chain/` — live/OTA boot-chain and offline repaired-image summary
- `sanitized/stock-adb-toggle/` — accepted stock ADB-toggle semantic, HCI, differential, and grammar summary

The protected-companion r22–r24.1 results are published primarily under
[`docs/research/`](../docs/research/README.md). Hash-only native-loader
provenance is also present in `manifests/` and `sanitized/native-loader/`.

## Excluded material

- PCAP/PCAPNG and TLS key logs
- raw HTTP/WebSocket payloads, logcat, bugreports, and HCI logs
- account tokens, IDs, serials, Bluetooth addresses, and location
- APKs, native libraries, decompiled trees, and proprietary DEX
- memory dumps, absolute runtime addresses, and process maps
- ADB host keys, authorization files, block maps, partition images, and patched boot images
