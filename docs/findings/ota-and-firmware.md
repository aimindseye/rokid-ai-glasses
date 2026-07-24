# OTA & Firmware

This page describes the OTA packaging, partition layout, boot chain, verified
boot, recovery environment, fastbootd architecture, and patch-risk findings for
the tested non-display Rokid AI Glasses Style.

The exact stock update targets:

```text
1.22.009-20260710-150201
```

The work was offline. No OTA was installed, no recovery or fastboot command was
issued to the glasses, no partition was written, and no slot was changed.

## OTA package

The package is a signed Android A/B OTA:

```text
ota-type=AB
pre-device=glasses
post-build=1.22.009-20260710-150201
```

No source-build constraint was present, supporting classification as a full
rather than incremental OTA.

Verified hashes:

```text
outer OTA:
163ab2058d8e8789f82e962c7bfccbe6ca9725437d15adaf4bc4a811bafc94e5

payload.bin:
7cd13cca5ad530207ad42aec188ddbe8187f01716b2e54a228e9612e25321a24

metadata:
b48d9d6d54e5362e08e2facaa4ec5d152c16301273482f20a66135f77476cfba
```

## Partition inventory

| Partition | Approximate image size |
|---|---:|
| `boot` | 101 MB |
| `dtbo` | 25 MB |
| `imagefv` | 16 KB |
| `modem` | 48 MB |
| `odm` | 1.1 MB |
| `product` | 761 MB |
| `recovery` | 105 MB |
| `system` | 853 MB |
| `system_ext` | 308 MB |
| `uefi` | 2.7 MB |
| `vbmeta` | 8 KB |
| `vbmeta_system` | 4 KB |
| `vendor` | 614 MB |
| `vendor_boot` | 101 MB |
| `vendor_dlkm` | 65 MB |
| `xbl` | 983 KB |
| `xbl_config` | 148 KB |
| `xbl_ramdump` | 700 KB |

No separate `init_boot` partition was present.

The filesystems are described as separate read-only image mounts. The evidence
does not justify calling the layout dynamic partitions.

## Boot images

The stock boot image uses Android boot header version 3:

```text
Android version:       12
security patch level:  2024-07
partition size:        100663296 bytes
kernel size:           47331340 bytes
ramdisk size:          1922154 bytes
```

Stock boot SHA-256:

```text
31f071baf83381c78d007b4849944b2778e49899d28beae2734c55b93ec82d3e
```

Recovery contains `recovery`, `adbd`, `minadbd`, `update_engine_sideload`,
`fastbootd`, recovery fastboot libraries, and generic swipe-related menu code.

Recovery SHA-256:

```text
aed5c2ec43b6a8e7c9d5483a3dd91d7f3acef958312bd7bf4f454c60e23b4102
```

`vendor_boot` uses header version 3 and contains the vendor ramdisk, device tree,
and Qualcomm USB-controller configuration.

Vendor boot SHA-256:

```text
c586a8bed81d731a4a1f1292c38071f6e0d3bca336809474d9eee0ce88d6d92a
```

## Verified Boot

Top-level `vbmeta` uses:

```text
SHA256_RSA4096
```

It protects the boot-related images and chains recovery and `vbmeta_system`.
`vbmeta_system` protects system, product, and system-extension images.
Vendor, vendor-DLKM, and ODM use hashtree descriptors.

The stock boot image matches the digest in Rokid's signed top-level AVB
metadata.

```text
vbmeta:
d17b2ace773b74ab3e149b4b50709e033840e9c2a7170e945f998c77296a201a

vbmeta_system:
dbbbe035833e445cc1f7ebc3ed1ddd39f23ccbed0c8cc62155be01285ad8534b
```

## OTA signing and recovery trust

The OTA is signed with a self-issued Rokid System certificate. The package
certificate matches a certificate trusted by the exact recovery environment.

This makes the stock OTA a credible signed recovery-sideload candidate for the
matching device family. It does not prove that same-build reinstall is
accepted, that it repairs slot state, or that it repairs USB debugging.

The stock OTA remains an emergency research candidate, not an approved first
repair step.

## Normal USB behavior

The normal boot ramdisk defaults persistent USB configuration to `none`.
Recovery also defaults to `none` and enables ADB, sideload, or fastboot through
mode-specific configfs transitions.

The USB-ADB control path is documented in
[Glasses OS & Services](glasses-android-os-and-adb.md).

## Fastbootd

The recovery environment contains fastbootd and calls the `IFastboot` HAL.
Core fastbootd contains ordinary partition operations; the vendor HAL supplies
vendor-specific hooks and metadata.

Only one visible HIDL passthrough implementation candidate was recovered, with
an `impl-mock` library name. Static evidence did not prove runtime selection.

```text
fastbootd architecture present: yes
ordinary core flash handlers present: yes
runtime partition exposure and lock enforcement: unresolved
safe flashing authorization: no
```

## Recovery menu and input limits

The exact recovery contains standard menu labels including:

```text
Reboot system now
Apply update from ADB
Apply update from SD card
Wipe data/factory reset
Wipe cache partition
Mount /system
View recovery logs
Run graphics test
Run locale test
Enter fastboot
Power off
```

Generic swipe-capable recovery UI support is present. Offline analysis did not
close the initial selection, gesture direction, arm evdev mapping, top-button
keycode, press behavior, or reliable no-display feedback.

Blind recovery navigation remains outside the approved boundary.

## Research-only Magisk patch

A research-only image was generated from the exact stock boot image using
Magisk 30.7 on a Pixel phone. It was never installed on the glasses.

The patch preserved full partition size, kernel size, and a parseable boot
header. It did not preserve AVB integrity:

```text
embedded descriptor size stale:    yes
embedded descriptor digest stale:  yes
matches Rokid signed boot digest:   no
AVB verification status:            failure
```

The patched ramdisk also embedded:

```text
PREINITDEVICE=sda8
```

That came from the Pixel patching environment and is not qualified for the
glasses.

```text
RESEARCH_ONLY_NEVER_FLASH=YES
```

Gross partition truncation, gross boot-header damage, and kernel corruption
were ruled out for the analyzed image. The leading possible failure stages are
fastbootd rejection, bootloader enforcement of Rokid's signed digest, or later
slot bootability effects. The exact stage remains unresolved without the
researcher's complete fastboot transcript.

## Safety boundary

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
