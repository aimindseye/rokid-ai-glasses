# OTA Boot-Chain and Offline Boot-Image Research

This directory publishes sanitized, hash-only findings from a read-only
comparison of the running glasses build, its matching full A/B OTA, and an
offline Magisk boot-image repair. Partition images, patched images, raw block
maps, device identifiers, and private workspaces are not published.

## Accepted result

```text
LIVE_BUILD_EQUALS_OTA_BUILD=YES
LIVE_VBMETA_CHAIN_EQUALS_OTA_VBMETA_CHAIN=YES
ACTIVE_SLOT=_b
ADB_SHELL_ACTIVE_PARTITION_READ=DENIED
ADB_SHELL_ACTIVE_PARTITION_WRITE=DENIED
OFFLINE_REPAIRED_MAGISK_CANDIDATE=ACCEPTED
DEVICE_BOOT_ATTEMPTED=NO
DEVICE_FLASH_ATTEMPTED=NO
```

## Read next

- [Validated findings](ota-boot-chain-and-offline-magisk-validation.md)
- [Machine-readable status](runtime-status-summary.json)
- [Hash-only provenance](evidence-hashes.txt)

The repaired image is an offline research artifact. Its local AVB footer uses
algorithm `NONE`; it is not OEM-signed, and the stock top-level vbmeta does not
authenticate its modified boot content.
