# Glasses Android OS and USB ADB

## Finding

The tested US non-display Rokid AI Glasses Style unit is a complete Android 12
computer, not only a Bluetooth audio/camera peripheral.

```text
Model:        RG-glasses
Device:       glasses
Board:        neo
ABI:          arm64-v8a
Android/API:  12 / 32
Build:        user / release-keys
Kernel:       5.10.209
```

The retail unit exposed RSA-protected USB ADB through the original Rokid
Data/Debug cable. It appeared as `device`, indicating an authorized host.

## Captured ADB state

```text
ro.secure=1
ro.debuggable=0
ro.adb.secure=1
persist.sys.usb.config=adb
sys.usb.config=adb
global.adb_enabled=1
global.adb_wifi_enabled=0
```

This is a production build with regular shell ADB, not a `userdebug` build with
normal `adb root`. Wireless ADB was disabled and no ADB TCP port was configured.

The persistent USB property indicates the captured default, but it can still be
changed by privileged vendor software, a reset, or an update.

## Boot qualification

The same production build reported:

```text
ro.boot.verifiedbootstate=orange
ro.boot.vbmeta.device_state=unlocked
```

The origin of this state is unknown. No claim is made that the researcher
unlocked the device. No flash, relock, root, fastboot, or verified-boot change
was attempted.

## Storage boundary

The glasses used separate immutable Android image mounts and an approximately
19 GB writable data volume with about 18 GB free during collection. This
repository intentionally omits raw block-device maps and all partition images.

## Development implication

The confirmed USB path enables normal Android development experiments:

- installing a signed test application;
- reading application logs;
- inspecting public Android capabilities;
- running official Rokid glasses-side demos when compatible.

It does not establish public-SDK compatibility or permission to call privileged
Rokid services. Those questions belong to Test 18.

## Operational baseline

The Pixel 7 remains the dedicated paired development phone. Developer Mode and
USB ADB are left enabled while development is active. The S25 daily-driver
migration is deferred until the target applications work end-to-end on Pixel.

See [Test 17](../tests/17-glasses-os-adb-and-network-exposure.md).

<!-- TEST18_USB_ADB_STATIC_START -->
## Test 18 static control-path follow-up

Offline analysis of the exact stock software identified the
`settings_developer_mode` key and the glasses-side enable/disable writes. The
enable path sets `persist.vendor.adb=true` and writes global ADB state `1`; the
available disable path sets `persist.vendor.adb=false` without a matching
global-state `0` write. This creates a credible stale-state hypothesis, but it
does not reveal the current live value on the glasses.

The relevant Rokid packages statically resolve to `priv_app`, and
`persist.vendor.adb` maps to `adbd_config_prop`. Direct authorization after
compiled-policy attribute expansion remains unresolved.

Real boot inputs showed charger-related generic debug-board detection but no
direct path to ADB or an official cable identifier. Cable/contact and
firmware/gadget-state explanations both remain open.

See [Test 18](../tests/18-usb-adb-control-and-cable-analysis.md) and the
[consolidated control-path finding](usb-adb-control-path-and-stale-state.md).
<!-- TEST18_USB_ADB_STATIC_END -->
