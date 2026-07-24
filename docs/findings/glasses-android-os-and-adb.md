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

<!-- USB_ADB_CONTROL_STATIC_START -->
## USB ADB control-path follow-up

Offline analysis of the exact stock software identified the glasses-side
Developer Mode key:

```text
settings_developer_mode
```

The recovered enable path performs:

```text
persist.vendor.adb=true
Settings.Global.adb_enabled=1
```

The recovered disable path performs:

```text
persist.vendor.adb=false
```

No matching `Settings.Global.adb_enabled=0` write was found in the available
disable method. This makes a stale state statically possible:

```text
phone or framework state: enabled
vendor ADB property:      false
```

The implementation does not reveal the current live value or prove which
branch most recently executed.

### Runtime domain and property boundary

The relevant Rokid packages statically resolve to `priv_app`:

```text
com.rokid.os.sprite.assistserver
com.rokid.cxrservice
com.rokid.sysconfig
```

The property maps to:

```text
persist.vendor.adb → adbd_config_prop
```

The reviewed policy sources contained neither a fully expanded direct allow
rule nor an explicit prohibition. Direct authorization remains unresolved
pending compiled-policy attribute expansion or future authorized runtime
evidence. A missing text-policy match is not proof of denial.

### Cable and debug-board boundary

The real `dtbo`, `vendor_boot`, and exact earlier debug-board binary candidate
were analyzed.

Generic debug-board detection exists in charger-related code, but no bounded
same-function or same-device-tree-node path connected it to:

- `persist.vendor.adb`;
- `adbd`;
- USB gadget activation; or
- an official Rokid cable identifier.

The current cable model is reportedly used successfully by multiple other
owners. That lowers the probability of a model-wide incompatibility, but does
not eliminate an individual cable, contact, alignment, adapter, or
unit-specific connector issue.

Current classification:

```text
special firmware cable-code check: not proven
cable/contact cause:               not ruled out
firmware/USB-gadget-state cause:   not ruled out
```

### Repair-app feasibility

No exported, unprotected glasses-side component was proven to reach the
Developer Mode setter. A normal user-installed glasses APK is therefore not
assumed capable of directly changing the protected property or secure global
ADB state.

A phone-side companion remains a plausible research direction:

```text
query current state
send settings_developer_mode=off
wait for positive reply
send settings_developer_mode=on
wait for positive reply
query current state again
```

It is not implementation-ready. Exact CXR framing, authentication, device
addressing, request correlation, and reply semantics remain open.

The replay could repair a stale control-plane mismatch. It cannot repair an
incompatible cable, failed contact, failed USB controller, or lower-level
gadget executor that ignores the property.

### Recovery boundary

Recovery contains ADB, sideload, fastbootd, and a generic swipe-capable menu,
but the non-display gesture mapping and reliable exit sequence are unresolved.
Blind recovery navigation, sideload, fastboot, flashing, and slot changes
remain outside the approved boundary.
<!-- USB_ADB_CONTROL_STATIC_END -->
