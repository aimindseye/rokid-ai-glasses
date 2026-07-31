# Project Status Through Test 20 r2.1 Implementation Readiness

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-07-31 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Validated |
| Last reviewed | 2026-07-31 |

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
| Test 19 CXR-L firmware comparison | PASS on firmware 1.22 and 1.23; no tested regression | [Final findings](developer/companion-app/test-19-r2-final-findings.md) |
| Test 20 CXR-L 1.0.1 static capability census | Corrected r1.2 publication accepted | [Published census](research/connection-protocol/publication/test20-r1-cxr-l-capability-census.md) |

## Current engineering boundary

| Capability | Current result |
|---|---|
| Direct CXR-M connection | Diagnostic r1 run retained; ownership result withdrawn |
| Hi Rokid CXR-L authorization and connection | PASS on firmware 1.22 and 1.23 through fallback-assisted service bind; r2.4 identity and disconnect repairs physically validated |
| CXR-L 1.0.1 static capability census | 72 classes/interfaces and 594 members inventoried; corrected nine-member runtime boundary published |
| Hi Rokid coexistence | PASS after both controlled firmware runs |
| Independent local photo capture | Not yet tested |
| Independent microphone and speaker paths | Not yet tested |
| CXR-L AI-assist start/stop callbacks in a custom app | Test 20 r2.1 repaired implementation prepared; physical qualification not yet performed |
| Offline local AI round trip | Not yet tested |
| Minimal on-glasses APK | Not yet tested |
| Proven custom-firmware recovery | Not established |
| Complete replacement companion | Not built |
| Common device–hub–brain platform | Architecture defined; vertical slice not built |

## Immediate next phase

Test 20 r1 is complete through the corrected r1.2 GitHub publication. The first
r1 sanitized publication remains withdrawn; only the r1.1 repaired census is
authoritative.

Test 20 r2.1 closes the public-artifact fixture and rollback-cleanup defects. Test 20 r2 remains one bounded CXR-L `CUSTOMAPP` attempt that passively
observes exactly two ordered AI-assist start/stop callback cycles. It remains
`READY_FOR_CONTROLLED_PHYSICAL_RUN`, not accepted, until the governed build,
install, callback-order, timeout, clean-disconnect, privacy, and Hi Rokid recovery
gates pass. Camera, audio streaming, custom commands, custom views, provider
access, glass-app management, and native/JNI behavior remain untested.

Custom firmware remains a later conditional track. Prefer stock firmware plus a
custom phone app, then a minimal on-glasses APK, before persistent firmware
modification.

## Historical release preservation

The accepted r25.2 connection-only, r25.3 stock-toggle, boot-chain,
native-loader, protected-application, Test 19, and Test 20 publications remain
under [Research](research/README.md). Documentation closures do not rewrite
private or historical evidence.
