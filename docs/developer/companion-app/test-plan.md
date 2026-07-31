# Companion-App Qualification Test Plan

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Test 19 — CXR-M compatibility gate

Qualify initialization, discovery, connection, device-status queries, clean
disconnect, and reconnect after phone and glasses restarts.

Required terminal outcomes:

```text
CUSTOM_APP_CXR_M_INITIALIZATION=PASS
CUSTOM_APP_DEVICE_DISCOVERY=PASS
CUSTOM_APP_DEVICE_CONNECTION=PASS
CUSTOM_APP_HARDWARE_STATUS_QUERY=PASS
CUSTOM_APP_CLEAN_DISCONNECT=PASS
CUSTOM_APP_RECONNECT_AFTER_REBOOT=PASS
```

## Test 20 — Hi Rokid ownership and coexistence

Compare Hi Rokid connected, backgrounded, force-stopped, and recovering states.
Identify whether the custom client can share, acquire, or exclusively own the
session.

## Test 21 — Camera capture without Rokid cloud

Trigger one glasses photo, receive it locally, measure latency and format, and
repeat with public internet blocked while local connectivity remains available.

## Test 22 — Microphone and speaker paths

Qualify input, output, interruption, sustained reliability, and full-duplex
echo behavior.

## Test 23 — Physical controls

Map press, release, long-press, camera, touch, assistant, wear, charge, and
available lifecycle events without assigning semantics beyond observed data.

## Test 24 — Custom AI interaction

Route one physical activation through local voice/image capture to a synthetic
local backend and return a spoken response without starting the stock cloud
assistant.

## Test 25 — Offline and privacy boundary

Block public internet and Rokid endpoints while preserving local LAN or
Tailscale access. Prove connection, capture, local request, response playback,
and absence of unexpected media upload.

## Test 26 — Lifecycle and recovery

Exercise reboot, Bluetooth cycling, force-stop, permission changes, range loss,
power loss, interrupted transfer, backend outage, and authentication expiry.
