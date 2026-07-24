# OTA & Firmware

This page summarizes the OTA packaging, firmware layout, boot chain, recovery
environment, fastbootd architecture, and patch-risk findings for the tested
non-display Rokid AI Glasses Style.

The exact stock update targets:

```text
1.22.009-20260710-150201
```

The work was performed offline. No OTA was installed, no recovery or fastboot
command was issued to the glasses, no partition was written, and no slot was
changed.

Exact byte counts, hashes, header fields, AVB descriptors, and stock-versus-
patched comparison values are collected in the
[compact technical appendix](ota-and-firmware-technical-appendix.md).

## OTA package and exact byte sizes

The package is a signed Android A/B OTA:

```text
ota-type=AB
pre-device=glasses
post-build=1.22.009-20260710-150201
```

No source-build constraint was present, supporting classification as a full
rather than incremental OTA.

The outer package and embedded payload were validated by exact size and hash.
The payload uses Android's `CrAU` payload format version 2.

## Partition inventory

The payload contains boot-chain, modem, Android system, vendor, recovery, and
Qualcomm bootloader-related partitions.

No separate `init_boot` partition was present.

The filesystems are best described as separate read-only image mounts. The
available evidence does not justify labeling the layout as dynamic partitions.

## Boot-image structures

The stock boot image uses Android boot header version 3 and targets Android 12
with the July 2024 security patch level.

Recovery is also a header-v3 image and primarily carries a recovery ramdisk.
`vendor_boot` uses header version 3 and contains the vendor ramdisk, DTB, and
Qualcomm USB-controller configuration.

The detailed image sizes, ramdisk sizes, DTB size, hashes, and meaningful boot
image boundary are in the technical appendix.

## Image hashes

Public provenance is hash-only. The raw OTA, payload, boot images, extracted
filesystems, APKs, and decompiled trees remain private.

The appendix lists the exact SHA-256 values for:

```text
outer OTA
payload.bin
metadata
boot.img
dtbo.img
recovery.img
vendor_boot.img
vbmeta.img
vbmeta_system.img
```

## AVB topology and descriptors

Top-level `vbmeta` uses:

```text
SHA256_RSA4096
```

It directly protects the boot-related images and chains recovery and
`vbmeta_system`.

`vbmeta_system` protects the system, product, and system-extension images.
Vendor, vendor-DLKM, and ODM are protected by hashtree descriptors.

The stock boot image matches the digest recorded in Rokid's signed top-level
AVB metadata.

The appendix records the boot descriptor's meaningful image size, salt,
digest, and the rollback-index locations used by the chained metadata.

## Recovery and fastbootd

Recovery contains:

- `recovery`;
- `adbd`;
- `minadbd`;
- `update_engine_sideload`;
- `fastbootd`;
- fastboot HAL libraries;
- standard recovery-menu and swipe-related UI strings.

Core fastbootd contains ordinary partition operations. The vendor HAL supplies
vendor-specific hooks and metadata rather than the basic writer.

Static evidence did not prove which fastboot HAL implementation loads at
runtime, which partitions are exposed, or how lock enforcement behaves on this
device.

Generic swipe-capable recovery UI support is present, but the non-display
gesture direction, arm evdev mapping, top-button keycode, press behavior, and
reliable exit sequence remain unresolved.

## OTA signing and sideload trust

The OTA is signed with a self-issued Rokid System certificate. The package
certificate matches a certificate trusted by the exact recovery environment.

This makes the stock OTA a credible signed recovery-sideload candidate for the
matching device family.

It does not prove that:

- same-build reinstall is accepted;
- equal-build reinstall repairs slot metadata;
- every device-specific state is preserved;
- USB debugging is repaired;
- blind recovery navigation is safe.

The stock OTA remains an emergency research candidate, not an approved first
repair step.

## Magisk patch comparison

A research-only boot image was generated from the exact stock boot image using
Magisk 30.7 on a Pixel phone. It was never installed on the glasses.

The patch preserved the full partition size and kernel size, but did not
preserve AVB consistency:

```text
embedded descriptor size stale:    yes
embedded descriptor digest stale:  yes
matches Rokid signed boot digest:   no
AVB verification:                   failed
```

The patched ramdisk also embedded:

```text
PREINITDEVICE=sda8
```

That value came from the Pixel patching environment and is not qualified for
the glasses.

Gross partition truncation, gross boot-header damage, and kernel corruption
were ruled out for the analyzed image.

The leading possible failure stages are:

1. fastbootd rejects a locked or internally inconsistent AVB image;
2. writing succeeds, but the bootloader rejects the image because it does not
   match Rokid's signed top-level boot digest;
3. failed boot attempts affect slot bootability or return the device to a
   limited fastboot state.

The exact stage remains unresolved without the original researcher's complete
fastboot transcript.

## Safety conclusions

The present research does not authorize:

```text
blind recovery entry
blind recovery navigation
OTA sideload
fastboot commands
partition flashing
vbmeta modification
verified-boot disabling
slot changes
patched-boot installation
```

The normal USB-ADB control path, stale-state hypothesis, cable boundary, and
repair-app feasibility are documented in
[Glasses OS & Services](glasses-android-os-and-adb.md).
