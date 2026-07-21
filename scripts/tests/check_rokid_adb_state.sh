#!/usr/bin/env bash
set -euo pipefail

command -v adb >/dev/null 2>&1 || {
  echo "ERROR: adb was not found in PATH." >&2
  exit 1
}

serial="$(
  adb devices -l |
  awk '$2 == "device" && /model:RG_glasses/ {print $1; exit}'
)"

if [ -z "$serial" ]; then
  echo "RG_glasses ADB connection: NOT PRESENT"
  adb devices -l
  exit 2
fi

echo "RG_glasses ADB connection: PRESENT"
echo "Host authorization state: device"
echo
for prop in \
  persist.sys.usb.config sys.usb.config sys.usb.state \
  ro.adb.secure ro.secure ro.debuggable \
  service.adb.tcp.port persist.adb.tcp.port; do
  value="$(adb -s "$serial" shell getprop "$prop" | tr -d '\r')"
  printf '%-28s %s\n' "$prop" "${value:-<empty>}"
done

for setting in adb_enabled adb_wifi_enabled development_settings_enabled; do
  value="$(
    adb -s "$serial" shell settings get global "$setting" 2>/dev/null |
    tr -d '\r'
  )"
  printf '%-28s %s\n' "global.$setting" "${value:-<empty>}"
done

echo
echo "No device setting was changed."
