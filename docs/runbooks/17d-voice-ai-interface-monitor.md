# Runbook 17D — Voice-AI Passive Interface Monitor

## Purpose

Observe whether one normal stock voice-assistant question activates a glasses
Wi-Fi, P2P, Wi-Fi Aware, or routed IP interface.

This is passive monitoring. It does not enable wireless ADB or contact any
listener.

## Procedure

Select `RG_glasses`, then run a three-minute monitor:

```bash
GLASSES_SERIAL="$(
  adb devices -l |
  awk '$2 == "device" && /model:RG_glasses/ {print $1; exit}'
)"

OUT="$HOME/rokid-nettest/private/test17d-voice-interface-$(date -u +%Y%m%dT%H%M%SZ).txt"
mkdir -p "$(dirname "$OUT")"
chmod 700 "$(dirname "$OUT")"

for i in $(seq 1 180); do
  {
    echo "=== SAMPLE $i $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    adb -s "$GLASSES_SERIAL" shell \
      'ip -br addr; echo "-- routes --"; ip -4 route; echo "-- listeners --"; ss -ltn'
    echo
  } >>"$OUT" 2>&1
  sleep 1
done
```

During the monitor, ask exactly one ordinary voice question. Do not request a
photo.

## Review

```bash
grep -nE \
  'wlan0.*UP|p2p0.*UP|wifi-aware0.*UP|inet [0-9]|src [0-9]|8341' \
  "$OUT"
```

Keep the raw file private because it may contain local addressing if an
interface activates.

## Published result

The accepted run showed only the persistent port-8341 listener. No target
interface activated and no IPv4 route appeared.
