# Firmware Inventory

<!-- wiki-status: audience=reference; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Reference |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## What this page records

This is an index of qualified firmware and boot-chain evidence, not a download
catalog and not a flashing guide.

| Area | Qualified result |
|---|---|
| Installed build identity | Recorded in the Test 17 and boot-chain evidence sets |
| Full OTA correspondence | Exact running build and supplied full OTA matched in scope |
| Vbmeta chain | Qualified 11,904-byte live/OTA match |
| Active partition access from regular ADB shell | Read and write denied in tested scope |
| Magisk candidate | Repaired and accepted offline only |
| Device boot or flash | Not attempted |
| Proven restoration path | Not established |

## Authoritative detail

- [Firmware and OTA finding](../findings/ota-and-firmware.md)
- [Technical OTA appendix](../findings/ota-and-firmware-technical-appendix.md)
- [Boot-chain research](../research/boot-chain/README.md)
