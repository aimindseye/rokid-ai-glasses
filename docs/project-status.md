# Project Status Through r26.0

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


This page separates completed stock-workflow and transport qualification from
replacement-app, on-glasses application, firmware, and common-platform work.

## Completed or substantially closed

| Area | Status | Evidence |
|---|---|---|
| First launch, login, pairing, model routing | Complete in documented scope | [Test matrix](tests/test-matrix.md) |
| Translation architecture and routing | Complete in documented scope | [Translation tests](tests/10-translation-overview.md) |
| Voice assistant route comparison | PASS | [Test 14A-r2](tests/14a-r2-manual-voice-base-model.md) |
| OTA checks and manifest behavior | PASS | [Test 14B](tests/14b-firmware-update-discovery.md) |
| Visual capture, upload, routing, follow-up, retention | PASS | [Test 15](tests/15-visual-ai-architecture-routing-retention.md) |
| Background services and data-sharing categories | PASS | [Test 16](tests/16-android-background-services-package-lineage-data-sharing.md) |
| Glasses Android, USB ADB, local services, passive network exposure | PASS | [Test 17](tests/17-glasses-os-adb-and-network-exposure.md) |
| Protected loader, class origin, and bounded caller census | Accepted bounded closure | [Research](research/README.md) |
| Independent RFCOMM connection-only lifecycle | Device-qualified | [Final closure](research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md) |
| HCI zero-application-payload census | TX 0, RX 0 | [Runtime status](research/connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json) |
| Stock ADB disable/restore semantics | Proven in bounded scope | [Findings](research/connection-protocol/stock-adb-toggle/findings.md) |
| Exact observed stock ADB-toggle frame grammar | Accepted for four messages | [Runtime status](research/connection-protocol/stock-adb-toggle/r25.3.1.3-runtime-status-summary.json) |
| Live/OTA vbmeta-chain correspondence | PASS in qualified scope | [Boot-chain research](research/boot-chain/README.md) |
| r26.0 audience-first wiki architecture | Implemented | [Documentation status](documentation-status.md) |

## Current engineering boundary

| Capability | Current result |
|---|---|
| Style-qualified CXR-M connection and status | Not yet tested |
| Hi Rokid coexistence and session ownership | Not yet tested |
| Independent local photo capture | Not yet tested |
| Independent microphone and speaker paths | Not yet tested |
| Physical control events in a custom app | Not yet tested |
| Offline local AI round trip | Not yet tested |
| Minimal on-glasses APK | Not yet tested |
| Proven custom-firmware recovery | Not established |
| Complete replacement companion | Not built |
| Common device–hub–brain platform | Architecture defined; vertical slice not built |

## Immediate next phase

Proceed with [Test 19: CXR-M compatibility](developer/companion-app/test-plan.md#test-19-cxr-m-compatibility-gate), then connection ownership, camera,
audio, controls, local AI, privacy, and lifecycle qualification.

Custom firmware remains a later conditional track. Prefer stock firmware plus a
custom phone app, then a minimal on-glasses APK, before any persistent firmware
modification.

## Historical release preservation

The accepted r25.2 connection-only, r25.3 stock-toggle, boot-chain,
native-loader, and protected-application publications remain unchanged under
[Research](research/README.md). The wiki revamp changes navigation and summaries,
not the underlying historical evidence.
