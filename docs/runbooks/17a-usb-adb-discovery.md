# Runbook 17A — USB ADB Discovery

## Purpose

Determine whether a non-display `RG_glasses` unit exposes authorized USB ADB
without changing device settings or restarting the glasses.

## Safety boundary

Do not run:

```text
adb root
adb remount
adb disable-verity
adb tcpip 5555
fastboot ...
reboot
setprop ...
settings put ...
```

Do not disconnect or migrate the paired phone during initial discovery.

## Physical setup

Use the original Rokid data/debug cable and a known data-capable adapter when
needed. A charge-only cable is insufficient.

## Identify the glasses

```bash
adb devices -l

GLASSES_SERIAL="$(
  adb devices -l |
  awk '$2 == "device" && /model:RG_glasses/ {print $1; exit}'
)"

test -n "$GLASSES_SERIAL" || {
  echo 'RG_glasses not found'
  exit 1
}
```

Keep the serial private.

## Read-only baseline

```bash
adb -s "$GLASSES_SERIAL" shell getprop ro.product.model
adb -s "$GLASSES_SERIAL" shell getprop ro.build.fingerprint
adb -s "$GLASSES_SERIAL" shell getprop ro.secure
adb -s "$GLASSES_SERIAL" shell getprop ro.debuggable
adb -s "$GLASSES_SERIAL" shell getprop ro.adb.secure
adb -s "$GLASSES_SERIAL" shell getprop persist.sys.usb.config
adb -s "$GLASSES_SERIAL" shell getprop sys.usb.config
adb -s "$GLASSES_SERIAL" shell settings get global adb_enabled
adb -s "$GLASSES_SERIAL" shell settings get global adb_wifi_enabled
```

## Interpretation

```text
state=device
  Authorized ADB host.

state=unauthorized
  ADB is exposed, but this host is not authorized.

persist.sys.usb.config=adb
  ADB was persistently configured at capture time; not proof of immutability.

ro.adb.secure=1
  RSA host authorization is enforced.

ro.debuggable=0
  Production build; normal adb root is not expected.
```

## Privacy

Do not publish the ADB serial, host keys, device authorization files, USB serial
strings, Bluetooth/Wi-Fi addresses, or complete raw USB dumps.
