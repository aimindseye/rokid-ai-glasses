# Test 19 r1 — Maven-Resolved CXR-M Qualification

> **Withdrawn:** This CXR-M workflow is retained for historical evidence only. Its ownership classification was invalidated by overlapping attempts and phase-attribution defects. Do not run it; use [Test 19 r2](test-19-r2-qualification.md).

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned physical qualification |
| Last reviewed | 2026-07-30 |

## Purpose

Resolve `com.rokid.cxr:client-m` from Rokid's Maven repository, preserve the
metadata/POM/AAR identity, attest the actual API surface, and determine whether
the SDK can connect to the tested non-display unit. The same run classifies
session ownership with Hi Rokid and proves whether SDK network activity remains
local during this connection-only phase.

## Source boundary

The Maven repository is `https://maven.rokid.com/repository/maven-public/`.
Community documentation currently names `client-m:1.0.8`, while its detailed
integration example names timestamped `0.0.x` builds. The live Maven index was independently observed listing releases through `1.2.1`, including `1.0.8`, `1.1.0`, and `1.1.1`. The runner therefore does not hard-code a documentation example: it downloads
`maven-metadata.xml`, chooses the repository release/latest value unless
`--sdk-version` is supplied, then downloads and hashes the matching POM and AAR.

The `buildwithfenna/rokid-docs` repository is provenance for the documented
Maven URL, minimum SDK 28, service UUID, permissions, and API examples. It is a
community source, not proof that this exact non-display unit is supported.

## Connection-only boundary

The app uses the documented methods:

- `CxrApi.getInstance()`;
- `initBluetooth(Context, BluetoothDevice, callback)`;
- `isBluetoothConnected()` and other allowlisted zero-argument status calls;
- `deinitBluetooth()`.

`connectBluetooth(...)` is inventoried but is not invoked during initial
connection because the community guide describes it as a reconnection API.
There is no direct `BluetoothSocket`, RFCOMM payload replay, camera, microphone,
file-transfer, AI, Developer Mode, firmware, or partition operation.

## Local-network privacy gate

The SDK requires Android network and Wi-Fi permissions, including `INTERNET`.
Test 19 r1 permits only Bluetooth and local/private-address SDK traffic. A
PCAPdroid connections CSV covering the run is required for a complete result.
Any public destination causes `LOCAL_NETWORK_PRIVACY_GATE=FAIL`.

The CSV analyzer treats loopback, link-local, RFC1918/private addresses, and
`.local`, `.lan`, `.home`, or `.internal` names as local. Unknown or public
hostnames/IPs remain reviewable in private evidence.

## Ownership phases

| Phase | Controlled state |
|---|---|
| `baseline_stock_connected` | Hi Rokid foreground and connected |
| `stock_background` | Hi Rokid backgrounded, not force-stopped |
| `stock_force_stopped` | Hi Rokid explicitly force-stopped |
| `custom_only` | Repeat custom-only cycle |
| `glasses_reboot_reconnect` | Glasses power-cycled |
| `phone_reboot_reconnect` | Phone rebooted and unlocked |
| `stock_recovery` | Test client stopped and Hi Rokid restored |

## Required markers

```text
CUSTOM_APP_CXR_M_ARTIFACT_AND_API_SURFACE=PASS
CUSTOM_APP_DEVICE_DISCOVERY=PASS
CUSTOM_APP_DEVICE_CONNECTION=PASS
CUSTOM_APP_HARDWARE_STATUS_QUERY=PASS
CUSTOM_APP_CLEAN_DISCONNECT=PASS
CUSTOM_APP_RECONNECT_AFTER_GLASSES_REBOOT=PASS
CUSTOM_APP_RECONNECT_AFTER_PHONE_REBOOT=PASS
HI_ROKID_STOCK_RECOVERY=PASS
LOCAL_NETWORK_PRIVACY_GATE=PASS
TEST19_R1_CXR_M_QUALIFICATION=PASS
```

## Execution

See the [Test 19 r1 research record](../../tests/test-19-r1-cxr-m-maven-and-ownership.md).

## Exit decision

A pass permits design work for the replacement companion lifecycle and the next
camera qualification. A connection-only pass with public traffic is not a
privacy pass. Artifact resolution, API incompatibility, model rejection, or
stock-recovery failure must be recorded as bounded blockers rather than worked
around with captured protocol replay.
