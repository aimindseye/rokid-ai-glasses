# Companion-App Qualification Test Plan

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Test 19 r2 — Hi Rokid CXR-L authorization and firmware comparison

Qualify the consumer-coexistence path through Hi Rokid `G1.11.11.0727` and
CXR-L `client-l:1.0.1`. Run the identical connection-only APK on firmware
`1.22.009-20260710-151201`, preserve evidence, update manually, and repeat on
`1.23.009-20260725-153201`.

Use the governed [Test 19 r2 runbook](test-19-r2-qualification.md). Ownership,
reboot, media, and APK-upload work is excluded. The old CXR-M Test 19 r1 runner
is disabled because its overlapping phases did not support a valid ownership
classification.

Required connection outcomes for each firmware are:

```text
TEST19_R2_AUTHORIZATION=PASS
TEST19_R2_CUSTOMAPP_SESSION_CONFIG=PASS
TEST19_R2_CXR_L_SERVICE_CONNECTION=PASS
TEST19_R2_GLASS_BLUETOOTH_CALLBACK=PASS
TEST19_R2_CLEAN_DISCONNECT=PASS
TEST19_R2_HI_ROKID_RECOVERY=PASS
TEST19_R2_QUALIFICATION=PASS
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
