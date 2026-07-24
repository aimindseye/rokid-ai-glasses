# OTA & Firmware — Technical Appendix

This appendix records the compact exact-value inventory used by the
[OTA & Firmware](ota-and-firmware.md) overview.

It publishes hashes and structural facts only. Raw OTA files, extracted
partitions, APKs, decompiled trees, and private logs remain outside the public
repository.

## A. OTA package and payload

| Field | Value |
|---|---:|
| Target build | `1.22.009-20260710-150201` |
| OTA type | `AB` |
| Pre-device | `glasses` |
| Outer package size | `981231124` bytes |
| Outer package MD5 | `516e268b35a3b9ac6359d6ae22a25edc` |
| Outer package SHA-256 | `163ab2058d8e8789f82e962c7bfccbe6ca9725437d15adaf4bc4a811bafc94e5` |
| `payload.bin` size | `981224705` bytes |
| `payload.bin` SHA-256 | `7cd13cca5ad530207ad42aec188ddbe8187f01716b2e54a228e9612e25321a24` |
| Metadata SHA-256 | `b48d9d6d54e5362e08e2facaa4ec5d152c16301273482f20a66135f77476cfba` |
| Payload magic | `CrAU` |
| Payload format version | `2` |
| Manifest length | `81860` bytes |
| Payload signature length | `267` bytes |
| Source-build constraint present | No |
| Full OTA classification | High confidence |

Both payload and metadata hashes matched the values declared by the package.

## B. Partition inventory

| Partition | Approximate image size |
|---|---:|
| `boot` | `101 MB` |
| `dtbo` | `25 MB` |
| `imagefv` | `16 KB` |
| `modem` | `48 MB` |
| `odm` | `1.1 MB` |
| `product` | `761 MB` |
| `recovery` | `105 MB` |
| `system` | `853 MB` |
| `system_ext` | `308 MB` |
| `uefi` | `2.7 MB` |
| `vbmeta` | `8192` bytes |
| `vbmeta_system` | `4096` bytes |
| `vendor` | `614 MB` |
| `vendor_boot` | `101 MB` |
| `vendor_dlkm` | `65 MB` |
| `xbl` | `983 KB` |
| `xbl_config` | `148 KB` |
| `xbl_ramdump` | `700 KB` |

`init_boot` was not present.

## C. Boot-image structures

### `boot.img`

| Field | Value |
|---|---:|
| Partition size | `100663296` bytes |
| Header version | `3` |
| Android version | `12` |
| Security patch | `2024-07` |
| Kernel size | `47331340` bytes |
| Ramdisk size | `1922154` bytes |
| Ramdisk compression | LZ4 |
| Meaningful image size | `49262592` bytes |
| SHA-256 | `31f071baf83381c78d007b4849944b2778e49899d28beae2734c55b93ec82d3e` |

### `recovery.img`

| Field | Value |
|---|---:|
| Header version | `3` |
| Kernel size | `0` bytes |
| Ramdisk size | `12807682` bytes |
| Ramdisk compression | LZ4 |
| SHA-256 | `aed5c2ec43b6a8e7c9d5483a3dd91d7f3acef958312bd7bf4f454c60e23b4102` |

### `vendor_boot.img`

| Field | Value |
|---|---:|
| Header version | `3` |
| Page size | `4096` bytes |
| Vendor ramdisk size | `6823108` bytes |
| DTB size | `364775` bytes |
| SHA-256 | `c586a8bed81d731a4a1f1292c38071f6e0d3bca336809474d9eee0ce88d6d92a` |
| USB controller | `a600000.dwc3` |
| SELinux boot mode | enforcing |
| Build variant | user |

## D. Image hashes

| Image | SHA-256 |
|---|---|
| `boot.img` | `31f071baf83381c78d007b4849944b2778e49899d28beae2734c55b93ec82d3e` |
| `dtbo.img` | `003549414ba29aefbc09be3d478a49b7986447d8022eded025041d27e805a31c` |
| `recovery.img` | `aed5c2ec43b6a8e7c9d5483a3dd91d7f3acef958312bd7bf4f454c60e23b4102` |
| `vendor_boot.img` | `c586a8bed81d731a4a1f1292c38071f6e0d3bca336809474d9eee0ce88d6d92a` |
| `vbmeta.img` | `d17b2ace773b74ab3e149b4b50709e033840e9c2a7170e945f998c77296a201a` |
| `vbmeta_system.img` | `dbbbe035833e445cc1f7ebc3ed1ddd39f23ccbed0c8cc62155be01285ad8534b` |

## E. AVB topology and descriptors

### Top-level `vbmeta`

| Field | Value |
|---|---|
| Algorithm | `SHA256_RSA4096` |
| Flags | `0` |
| Rollback index | `0` |
| Boot descriptor image size | `49262592` bytes |
| Boot descriptor salt | `cdaf…` |
| Boot descriptor digest | `fc7d…` |
| Recovery chain rollback-index location | `1` |
| `vbmeta_system` chain rollback-index location | `2` |
| Recovery chain key family | RSA-4096 |
| `vbmeta_system` chain key family | RSA-2048 |

The compact public appendix intentionally abbreviates the descriptor salt and
digest because their full values are already retained in the private governed
evidence. The important verified result is that the exact stock boot data
matches Rokid's signed descriptor.

### `vbmeta_system`

| Field | Value |
|---|---|
| Protected images | `system`, `product`, `system_ext` |
| Rollback index | `1720137600` |
| Interpreted patch date | `2024-07-05` |

Hashtree-protected images include `vendor`, `vendor_dlkm`, and `odm`.

## F. Recovery and fastbootd inventory

Confirmed recovery components include:

```text
system/bin/recovery
system/bin/adbd
system/bin/minadbd
system/bin/update_engine_sideload
system/bin/fastbootd
android.hardware.fastboot@1.1-impl-mock.so
```

Confirmed architectural findings:

```text
recovery ADB support:                         present
recovery sideload support:                    present
recovery fastbootd support:                   present
generic swipe-capable menu support:           present
ordinary flash handlers in fastbootd core:    present
runtime HAL selection:                        unresolved
physical gesture mapping:                     unresolved
safe blind navigation:                        no
```

## G. OTA signing and sideload trust

| Field | Value |
|---|---|
| Certificate subject/issuer | Rokid System, self-issued |
| Certificate SHA-256 | `9fc9844e46a7c2794ba561ee418e29f37add9604e0825e6b1c877007ee87a993` |
| Valid from | `2024-10-24` |
| Valid through | `2052-03-11` |
| Certificate trusted by exact recovery | Yes |
| Same-build reinstall accepted | Unresolved |
| Sideload approved for current unit | No |

## H. Stock-versus-Magisk comparison

The research-only patched image SHA-256 is retained here for provenance:

```text
943314b271e83c9298adc9f9451f1fc9ce135efab4a73c3a260d38f3cb4a127d
```

| Field | Stock | Patched |
|---|---:|---:|
| Full partition size | `100663296` | `100663296` |
| Kernel size | `47331340` | `47331340` |
| Ramdisk size | `1922154` | `1782365` |
| Ramdisk-size delta | — | `-139789` |
| Meaningful image size | `49262592` | `49123328` |
| Meaningful-size delta | — | `-139264` |
| Footer at repacked end | stock layout | Yes |
| Embedded descriptor image size | correct | stale |
| Embedded descriptor digest | correct | stale |
| Matches Rokid signed boot digest | Yes | No |
| AVB verification | Pass | Fail (`status=1`) |
| Pixel preinit embedded | No | Yes |
| `PREINITDEVICE` | — | `sda8` |

The patched image preserved the full partition container and kernel, but its
embedded descriptor remained inconsistent with the repacked boot content and
the top-level Rokid-signed digest.

```text
RESEARCH_ONLY_NEVER_FLASH=YES
```

## I. Safety conclusions

| Operation | Current status |
|---|---|
| Read-only offline analysis | Approved |
| No-restart cable A/B observation | Approved |
| Blind recovery entry/navigation | Not approved |
| OTA sideload | Not approved |
| Fastboot commands | Not approved |
| Slot changes | Not approved |
| `vbmeta` modification | Not approved |
| Patched boot installation | Not approved |
| Partition flashing | Not approved |
