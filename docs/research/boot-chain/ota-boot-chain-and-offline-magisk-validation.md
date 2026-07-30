# OTA Boot-Chain and Offline Magisk Validation

## Scope

The work used the exact full A/B OTA whose build fingerprint, incremental build,
and security-patch level matched the running glasses. All device collection was
read-only. No partition was read through a privileged path, written, flashed,
relocked, or temporarily booted.

## Live-to-OTA correspondence

The running device reported:

```text
build incremental: 1.22.009-20260710-150201
Android:           12
security patch:    2024-07-05
active slot:       _b
verified boot:     orange / unlocked
vbmeta hash alg:   sha256
vbmeta size:       11904 bytes
```

The SHA-256 of the exact 11,904-byte OTA-derived vbmeta chain equaled the live
bootloader-reported digest:

```text
438ae266c9a636cb12bee30bf551f7aa78213ef7f9c1f360b9ef24d23172ffab
```

The combined chain consisted of the top-level vbmeta structure, the recovery
vbmeta structure, and `vbmeta_system`. This proves byte identity of the loaded
vbmeta structures and the matching OTA structures. It does not independently
read back every byte of the active boot partition.

## ADB partition boundary

The active-slot boot, vendor-boot, recovery, DTBO, vbmeta, and vbmeta-system
block devices were root-only. The regular ADB shell could neither read nor write
them. The OTA-derived boot image therefore remains the canonical acquisition
source for offline analysis.

## Boot-image structure

The matching stock boot image is Android boot header version 3 with:

```text
kernel size:       47331340 bytes
ramdisk size:       1922154 bytes
OS version:        12.0.0
OS patch level:    2024-07
command line:      empty
partition size:    100663296 bytes
```

The generic ramdisk resides in `boot.img`; `vendor_boot`, recovery, DTBO, and the
vbmeta images are not Magisk patch targets for this build.

## Rejected earlier Magisk candidate

The earlier Magisk 30.7 candidate had correct source lineage but was rejected
for two environment-contamination defects:

1. its configuration contained `PREINITDEVICE=sda8`, while a live Magisk 30.7
   query on the glasses returned `metadata`; and
2. Magisk's Samsung DEFEX four-byte signature matched the non-Samsung Rokid
   kernel and changed three bytes in one instruction region.

The earlier candidate's backed-up `init` and stored stock-image SHA-1 matched the
accepted pristine Rokid boot image. The defect was therefore in the patching
result, not in source-image selection.

## Repaired offline candidate

The repaired candidate was constructed without rerunning the full Magisk patch
sequence:

- source boot image: exact matching OTA-derived `boot.img`;
- kernel: restored byte-for-byte from the pristine Rokid image;
- Magisk payload: version 30.7 / version code 30700;
- configuration: only `PREINITDEVICE=sda8` changed to
  `PREINITDEVICE=metadata`;
- CPIO differential: exactly one member changed, `.backup/.magisk`;
- compression: legacy LZ4 framing preserved and round-trip verified;
- boot header: version 3, Android 12.0.0, patch level 2024-07, empty command
  line; and
- final partition image size: 100,663,296 bytes.

The final unpacked kernel equals the pristine kernel, and the final unpacked
ramdisk equals the repaired Magisk ramdisk.

## AVB boundary

The repaired image has a self-consistent local hash footer and passes local
`avbtool verify_image` when presented under the descriptor's `boot.img` name.
The local vbmeta algorithm is `NONE`.

This does not provide an OEM signature. The stock signed top-level vbmeta still
authenticates the pristine boot digest, not the repaired image. The repaired
candidate therefore depends on the device's already-observed unlocked state and
remains an offline-only artifact pending a separately authorized boot decision.

## Final status

```text
SOURCE_BOOT_LINEAGE=PROVEN
LIVE_VBMETA_TO_OTA_CORRESPONDENCE=PASS
REPAIRED_KERNEL_EQUALS_PRISTINE=YES
REPAIRED_PREINITDEVICE=metadata
LOCAL_AVB_CONTENT_VALIDATION=PASS
OFFLINE_REPAIRED_CANDIDATE=ACCEPTED
DEVICE_BOOT_ATTEMPTED=NO
DEVICE_FLASH_ATTEMPTED=NO
FLASH_AUTHORIZATION=NO
```
