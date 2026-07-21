# Runbook 17E — Visual-AI Passive Interface Monitor

## Purpose

Determine whether a stock visual-AI request that captures a fresh image uses
Wi-Fi, Wi-Fi Direct, or Wi-Fi Aware on the glasses.

## Run

```bash
cd /path/to/rokid-ai-glasses
chmod +x scripts/tests/run_rokid_test17e_visual_ai_interface.sh
./scripts/tests/run_rokid_test17e_visual_ai_interface.sh
```

Defaults:

```text
Duration: 180 seconds
Interval: 0.5 seconds
Samples:  360
```

When prompted, point the glasses at a non-sensitive object, mark the start, ask
one visual question such as “What object am I looking at?”, wait for the full
answer, and mark the end.

## Output

The script separates:

```text
~/rokid-nettest/private/test17e-visual-ai-interface-<timestamp>/
~/rokid-nettest/sanitized/test17e-visual-ai-interface-<timestamp>/
```

The private tree may include raw interfaces, routes, counters, logs, timestamps,
addresses, and device/build details. Do not upload it.

The sanitized output reports only activation state, sample count, traffic
deltas, route presence, and whether port 8341 remained visible.

## Safety

The script does not:

- enable Wi-Fi or wireless ADB;
- run `adb root`, remount, or reboot;
- connect to TCP 8341;
- change system properties or settings.

## Accepted result

```text
Samples:                 360
wlan0 activated:         NO
p2p0 activated:          NO
wifi-aware0 activated:   NO
IPv4 route observed:     NO
port 8341 remained:      YES
```
