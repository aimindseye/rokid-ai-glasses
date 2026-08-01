# Developer Current Status

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-07-31 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Validated |
| Last reviewed | 2026-07-31 |

## Replacement companion boundary

| Capability | Current status |
|---|---|
| Stock pairing and binding behavior | Observed |
| Runtime RFCOMM endpoint attribution | Complete in accepted r25.2 scope |
| Independent RFCOMM open/close | Device-qualified |
| Channel identity | SCN 3, DLCI 6, MTU 990 |
| Application bytes in accepted connection-only attempt | Proven zero in both directions |
| Stock ADB-toggle outbound message family | Four qualified messages attributed and decoded |
| Reply, authorization, integrity, and session binding | Unresolved |
| Independent Developer Mode sender | Not implemented; replay prohibited |
| Direct CXR-M experiment | r1 evidence retained; ownership classification withdrawn; runner disabled |
| Hi Rokid CXR-L client | Test 19 r2 accepted: firmware 1.22/1.23 PASS, no tested regression, r2.4 runtime repairs physically validated |
| CXR-L 1.0.1 capability census | Test 20 r1.2 accepted: static census and corrected member-level publication complete |
| CXR-L AI-assist event callbacks | Test 20 r2.2 accepted: two ordered start/stop cycles, clean disconnect, and Hi Rokid recovery PASS |
| Independent camera capture | Not yet tested |
| Independent microphone and speaker path | Not yet tested |
| Complete Hi Rokid replacement | Not built |

## On-glasses and firmware boundary

| Capability | Current status |
|---|---|
| Android/API identity | Android 12/API 32 observed |
| USB ADB | RSA-protected transport qualified while Developer Mode enabled |
| Ordinary APK lifecycle on Style | Not yet qualified |
| Privileged permission boundary | Not yet mapped |
| Live/OTA vbmeta correspondence | Read-only match established for the qualified chain |
| Repaired Magisk candidate | Accepted offline only; never booted or flashed |
| Proven recovery path for custom firmware | Not established |

## Recommended next gate

Test 19 r2 is complete and publication-closed. Test 20 r1.2 remains the
immutable corrected static census with nine descriptor-exact runtime-qualified
members and two qualified Hi Rokid components. The original overbroad Test 20
r1 publication remains withdrawn.

Test 20 r2.2 publishes the accepted single-attempt physical qualification of
exactly two ordered `onGlassAiAssistStart()`/`onGlassAiAssistStop()` cycles. The
combined accepted CXR-L member boundary is now eleven descriptor-exact members:
nine from Test 20 r1.2 plus these two callbacks. The test application performed
no assistant invocation, cloud AI request, camera, microphone, media-stream,
custom-command, custom-view, provider, or glass-app-management operation.

Camera, audio streaming, custom commands, custom views, provider access,
glass-app management, and native/JNI behavior remain untested and require a
separately approved phase.

## Evidence

- [Project status](../project-status.md)
- [Test 20 r1 census guide](../tests/test-20-r1-cxr-l-capability-census.md)
- [Test 20 r1.1 classification repair](../tests/test-20-r1-1-cxr-l-classification-repair.md)
- [Test 20 r1.2 final publication](../tests/test-20-r1-2-cxr-l-final-publication.md)
- [Test 20 r2 event qualification](../tests/test-20-r2-cxr-l-event-control-plane-qualification.md)
- [Test 20 r2.1 apply repair](../tests/test-20-r2-1-public-artifact-rollback-repair.md)
- [Test 20 r2.2 final callback publication](../tests/test-20-r2-2-final-ai-assist-callback-publication.md)
- [Published capability census](../research/connection-protocol/publication/test20-r1-cxr-l-capability-census.md)
- [Published AI-assist callback summary](../research/connection-protocol/publication/test20-r2-cxr-l-event-summary.md)
- [Connection-protocol research](../research/connection-protocol/README.md)
- [Boot-chain research](../research/boot-chain/README.md)
