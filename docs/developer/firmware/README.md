# Firmware Research Track

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Current result

The running build and exact full OTA were matched in the read-only boot-chain
track, including the qualified 11,904-byte vbmeta chain. A repaired Magisk 30.7
boot candidate passed offline validation with the pristine Rokid kernel and
`PREINITDEVICE=metadata`.

The candidate is not OEM-signed, was never booted or flashed, and is not a
recovery proof.

## Required gates before persistent modification

1. Immutable partition and build inventory.
2. A/B slot and bootloader-variable census.
3. Complete stock restoration source.
4. Verified recovery from a deliberately non-booting test condition.
5. AVB, rollback-index, signing, and dm-verity analysis.
6. Temporary boot capability where available.
7. Preservation tests for camera, microphone, speaker, Bluetooth, Wi-Fi,
   charging, battery, buttons, TEE, calibration, and factory reset.

## Preferred progression

```text
stock firmware
→ custom phone app
→ small stock-firmware APK
→ minimally modified boot/system image
→ vendor-preserving custom system
→ full custom firmware only if sources and blobs permit it
```

## Evidence

- [Boot-chain research](../../research/boot-chain/README.md)
- [Offline validation](../../research/boot-chain/ota-boot-chain-and-offline-magisk-validation.md)
