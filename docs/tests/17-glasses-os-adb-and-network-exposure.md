# Test 17 — Glasses Android OS, USB ADB, Boot State, and Network Exposure

## Status

**PASS in the documented, read-only scope.**

This qualification covers the **US-tested, non-display Rokid AI Glasses Style**
unit. Results may differ across regions, consumer/enterprise firmware, hardware
revisions, and later updates.

| Subtest | Question | Result |
|---|---|---|
| 17A | Does the retail non-display model expose ADB over the original debug cable? | PASS — authorized USB ADB detected |
| 17B | What OS/build/security/boot/storage baseline is present? | PASS — Android 12 production build; boot properties reported orange/unlocked |
| 17C | Which local Rokid services and listeners run on the glasses? | PASS — privileged assistant stack and root TEE-domain listener observed |
| 17D | Does one normal voice-AI question activate a glasses IP interface? | NOT OBSERVED — no Wi-Fi, P2P, Wi-Fi Aware, or route |
| 17E | Does one fresh-image visual-AI question activate a glasses IP interface? | NOT OBSERVED across 360 half-second samples |
| 17F | Can the static development baseline and selected vendor APK hashes be preserved safely? | PASS — privacy gate passed; 8/8 private pulls matched device hashes |

Raw dumps, APKs, logs, addresses, host authorization material, device serials,
and private monitor files are not stored in this repository.

## 17A — USB ADB discovery

With the glasses still paired normally to a Pixel 7, the Mac enumerated two ADB
devices. Selecting the entry with `model:RG_glasses` identified the glasses:

```text
product:glasses
model:RG_glasses
device:glasses
transport:USB
```

The physical chain was:

```text
Mac USB-C port
  → USB-C-to-USB-A data adapter
  → original Rokid data/debug cable
  → glasses
```

The original data/debug cable is the strongest explanation for successful USB
enumeration. The adapter preserved the USB data path. The Pixel was the paired
companion phone but was not the ADB transport.

The official Rokid demo guide similarly instructs developers to connect a
Glass3 data debug cable and verify that Android Studio recognizes `Rokid
RG-glasses`.

References:

- <https://x-docs.rokid.com/docs/en/downloads/demo-guide.html>
- <https://x-docs.rokid.com/docs/en/faq/%E5%B8%B8%E8%A7%81%E9%97%AE%E9%A2%98.html>

### Authorization

The ADB state was `device`, not `unauthorized`. Android's RSA-protected ADB
model therefore considered the Mac authorized. No ADB host key or device-side
authorization file is public.

## 17B — Android, security, boot, and storage

### Build identity

```text
Manufacturer: Rokid
Brand:        Rokid
Model:        RG-glasses
Device:       glasses
Board:        neo
ABI:          arm64-v8a
Android:      12
API level:    32
Build type:   user
Build tags:   release-keys
Kernel:       5.10.209
```

Build fingerprint:

```text
Rokid/glasses/glasses:12/SKQ1.240613.001/1.22.009-20260710-150201:user/release-keys
```

The build timestamp identifier matches the OTA package-build identifier
observed in Test 14B, while other app/server surfaces exposed nearby but
different version strings.

### ADB security and persistence

```text
ro.secure=1
ro.debuggable=0
ro.adb.secure=1
persist.sys.usb.config=adb
sys.usb.config=adb
global.adb_enabled=1
global.adb_wifi_enabled=0
service.adb.tcp.port=<empty>
persist.adb.tcp.port=<empty>
```

Interpretation:

- this is a production `user` build, not `userdebug`;
- normal `adb root` is not expected;
- RSA host authorization is enabled;
- USB ADB is persistently configured at the captured state;
- wireless ADB and legacy TCP ADB were not enabled.

`persist.sys.usb.config=adb` is persistent configuration, not an immutable
promise. Rokid software, a firmware update, a reset, or the Developer Mode
control may still change it.

Android ADB reference:

- <https://developer.android.com/tools/adb>

### Reported verified-boot state

```text
ro.boot.verifiedbootstate=orange
ro.boot.vbmeta.device_state=unlocked
```

The tested unit therefore reported an orange/unlocked verified-boot state while
running a `user/release-keys` build. This investigation did not determine when
or how that state was established. It does not claim that the researcher
unlocked the device, that safe flashing is possible, or that root access is
available.

No fastboot, relocking, flashing, verified-boot modification, or partition
write was attempted.

### High-level storage layout

Android exposed separate read-only image mounts for the root/system,
`system_ext`, `product`, `vendor`, `vendor_dlkm`, and `odm` layers. The fully
allocated image mounts are normal for immutable Android system images and do
not indicate writable-storage pressure.

The writable data volume was approximately:

```text
Total: 19 GB
Used:  966 MB
Free:  18 GB
```

Additional metadata, persistent vendor, DSP, Bluetooth-firmware, and firmware
mounts were visible. A complete GPT/block-device map was neither required nor
published. No partition image was extracted.

## 17C — Local package and service architecture

### Package inventory

`pm list packages -3` returned no ordinary user-installed third-party package.
The following relevant applications were preloaded as system/product/vendor
software:

| Package | Private APK SHA-256 |
|---|---|
| `com.rokid.os.sprite.assistserver` | `53b5d85837650ba048bb95489180c9ce7638e710c8bc29454ece608438123e81` |
| `com.rokid.os.sprite.live` | `51672b655f858f1028e08bbe8028d5ae3539b0152a617fdda260d0991b69ee2f` |
| `com.rokid.sysconfig` | `e6f8dbad6a4c5e7f77864553784ad1098849fa83fc45eec70db5f9366e537b5e` |
| `com.rokid.cxrservice` | `177305c60d688ee2747227b61e12773e18f92b7b70b54f995734c4a42e938a5e` |
| `com.rokid.glass.ota` | `6bcb9c83243697481a08df9e57de1c5c4d54459dcaa051db9e9ad9fbd6fd0aaf` |
| `com.rokid.os.master.screenstream` | `685220ad37ffa97d603b9a2061fb59f426f1986f8f0809691681d4f110bf1410` |
| `com.rokid.os.sprite.launcher` | `96c6a6a6c02037786977c2982d62ee5b0972ade2032668ce3bf5e78e3b7cbccf` |
| `com.iap.mobile.ar_pay` | `966ad76351a1cf99935840cbc3556ae2d9a810fe31d55a2db9135f449e5fa3cc` |

The APK binaries remain private. Test 17F pulled all eight and confirmed that
each host-side SHA-256 matched the device-side SHA-256.

### Central assistant stack

The central process `com.rokid.os.sprite.assistserver` hosted active services
for:

```text
MasterAssistService
InstructService
SpriteMediaService
SystemFuncService
TtsService
PaymentService
WebServerService
RokidBluetoothService
SpriteWifiService
```

The glasses are therefore a complete Android device with on-device assistant,
media, system-control, Bluetooth, Wi-Fi, TTS, payment, OTA, camera, audio, and
screen-streaming components. The stock cloud AI flow still used the phone as
the observed network gateway.

### Payment subsystem clarification

The preloaded `com.iap.mobile.ar_pay` product application exposed
`Glass2PayService`, which was bound by the Rokid assistant server. The assistant
server also ran `PaymentService`.

This supports an on-glasses Rokid/AntPay origin for the earlier
`payment_binding` capability configuration. It does not demonstrate a bound
payment account, card data, balance, or transaction history. Google Wallet and
Samsung Wallet data were not observed.

### GateServiced and port 8341

The persistent listener was:

```text
0.0.0.0:8341
```

The socket table reported UID 0. The device simultaneously ran:

```text
Process:        GateServiced
Parent:         init
Executable:     /vendor/bin/GateServiced
UID/GID:        0 / 0
SELinux domain: u:r:tee:s0
NoNewPrivs:     0
Seccomp:        0
Capabilities:   full kernel-supported mask
```

`/vendor/etc/init/init.gateserviced.rc` defined that executable. Production
`/proc` restrictions blocked a direct socket-inode-to-process-FD mapping, so
the public report describes GateServiced as the **very-high-confidence owner**
of TCP 8341 rather than claiming an observed file-descriptor link.

Android `WebServerService` was not running its own internal server during the
capture. Its logs reported:

```text
needRunning:false
mServerRunning:false
openState:false
```

No request, probe, HTTP exchange, protocol payload, or fuzzing input was sent to
port 8341.

## 17D — voice-AI passive network monitor

One normal voice-assistant question was performed while the glasses interfaces,
routes, and listeners were sampled for approximately three minutes.

Observed:

```text
wlan0 activated:       NO
p2p0 activated:        NO
wifi-aware0 activated: NO
IPv4 route created:    NO
port 8341 listening:   YES
```

The tested voice workflow therefore did not create an IP path originating from
the glasses. This supports the phone-gateway sequence already observed in
phone-side captures:

```text
Glasses microphone → Bluetooth/control path → Hi Rokid → Rokid cloud
```

## 17E — visual-AI passive network monitor

One visual question requiring a fresh camera frame was performed while a
privacy-first script collected 360 samples at 0.5-second intervals.

```text
wlan0 activated:       NO
p2p0 activated:        NO
wifi-aware0 activated: NO
IPv4 route created:    NO
port 8341 listening:   YES
```

Combined with Test 15's phone-side evidence, this strongly supports the stock
visual path:

```text
Glasses camera → Rokid Bluetooth transport → Hi Rokid → object upload/cloud AI
```

A sub-half-second transition is theoretically possible, but no interface state,
route, or counter evidence of a meaningful IP session appeared.

## 17F — static development baseline

The final collector preserved:

- build, ADB, USB, verified-boot, and shell-security properties;
- package, permission, Binder, HAL, feature, camera, audio, input, display,
  sensor, Bluetooth, interface, listener, and init metadata;
- selected device-side APK hashes;
- optional private APK pulls and host/device hash comparison;
- a sanitized assertion set and hash-only private-evidence manifest.

Result:

```text
SANITIZED_PRIVACY_GATE=PASS
SELECTED_VENDOR_PACKAGES_PRESENT=8_OF_8
PRIVATE_APKS_PULLED=8_OF_8
HOST_DEVICE_APK_HASH_MATCH=8_OF_8
```

## Final assertions

```text
RETAIL_NON_DISPLAY_GLASSES_FULL_ANDROID=CONFIRMED
ANDROID_VERSION=12
BUILD_TYPE=user/release-keys
USB_ADB=CONFIRMED
ADB_RSA_PROTECTED=YES
ADB_ROOT=NO
USB_ADB_PERSISTENTLY_CONFIGURED_AT_CAPTURE=YES
WIRELESS_ADB_ENABLED=NO

VERIFIED_BOOT_STATE_REPORTED_ORANGE=YES
VBMETA_DEVICE_STATE_REPORTED_UNLOCKED=YES
FLASHING_OR_RELOCKING_TESTED=NO

ORDINARY_THIRD_PARTY_PACKAGES=0
PRIVILEGED_ROKID_SERVICE_STACK=CONFIRMED
ANTPAY_COMPONENT_PREINSTALLED=YES
PAYMENT_ACCOUNT_OR_CREDENTIALS_OBSERVED=NO

GATESERVICED_PRESENT_AS_ROOT_TEE_DOMAIN=YES
TCP_8341_LISTENER_PRESENT=YES
TCP_8341_OWNER_ATTRIBUTION=GATESERVICED_VERY_HIGH_CONFIDENCE
ACTIVE_EXTERNAL_INTERFACE_EXPOSING_8341=NO

VOICE_AI_ACTIVATED_GLASSES_IP_NETWORK=NOT_OBSERVED
VISUAL_AI_ACTIVATED_GLASSES_IP_NETWORK=NOT_OBSERVED
PHONE_AS_STOCK_AI_NETWORK_GATEWAY=STRONGLY_SUPPORTED
```

## Limitations

- One consumer unit and one firmware build were tested in the United States.
- The role of the Hi Rokid Developer Mode toggle in first-time authorization
  and future phone migration remains unresolved.
- The Pixel 7 remains the dedicated development phone; Pixel-to-S25 migration
  was deliberately deferred.
- No bootloader command, fastboot test, root attempt, remount, partition write,
  wireless-ADB enablement, or port-8341 request was performed.
- Stock voice and visual AI were tested; other workflows may explicitly
  establish Wi-Fi/P2P.
- Official enterprise SDK capability does not prove compatibility with this
  exact consumer firmware. SDK compatibility is deferred to Test 18.
