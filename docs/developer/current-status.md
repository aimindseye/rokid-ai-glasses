# Developer Current Status

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-08-02 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Validated |
| Last reviewed | 2026-08-02 |

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
| CXR-L media-plane feasibility | Test 20 r3.0.1 accepted: 23 descriptor-exact image/audio/service surfaces statically confirmed; runtime qualification not granted |
| CXR-L media no-payload preflight | Test 20 r3.1.1 accepted: service status, Bluetooth status, image/audio callback registration, 15-second quiet window, zero unsolicited media callbacks, clean disconnect, and Hi Rokid recovery PASS |
| CXR-L one-shot photo qualification | Test 20 final accepted: two-phase one-shot gate and image callback path proven; post-service-status callback re-registration is the canonical tested lifecycle |
| CXR-L static Binder boundary | Test 21 accepted: full static boundary closed for `client-l:1.0.1`; callback side 7 interfaces / 21 methods / 21 confirmations / 0 mismatches; authorization and session semantics remain unresolved |
| Independent camera capture | Qualified only through the custom CXR-L + Hi Rokid authorization/media-service path; direct/no-Hi-Rokid capture remains unqualified |
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

### Test 21 static Binder boundary

Test 21 is publication-closed. The accepted service/client Binder prerequisite plus callback closure establish the static CXR-L Binder boundary for `client-l:1.0.1`. The final callback result is 7/7 interfaces, 21/21 methods, 21/21 Stub ↔ Proxy confirmations, 21/21 Parcel contracts, and 0 transaction mismatches.

This is an interface/ABI result, not a claim that a complete Hi Rokid replacement is functional. Authorization semantics, session lifecycle, proprietary service implementation, and end-to-end compatibility remain unresolved. See the [Test 21 overview](../research/cxr/test21-static-binder-boundary-overview.md).

<!-- r27.1.0-canonical-tooling -->
## Repository/tooling consolidation gate

Test 21 is closed, but new device testing is intentionally paused during **R27 repository canonicalization**. R27.1 introduces `scripts/rokid-research` as the stable semantic front door while preserving historical revision scripts for provenance. No historical implementation is retired until preservation, unique-logic mapping, equivalence testing, documentation migration, and publication review pass.

See the [canonical tooling index](../research/tooling/README.md).

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

Test 20 r3.0.1 publishes the accepted read-only media-plane feasibility
census: eight client entry points, five callbacks, and ten media-service
contract members. Image and audio control/callback paths are statically
present, but parameter semantics and payload formats remain unresolved.
No media API was invoked, no payload was collected, and runtime qualification
was not granted.

Test 20 r3.1.1 publishes the accepted bounded service-status and no-payload
preflight. One governed physical attempt registered image and audio callback
interfaces, queried service version and version code, confirmed glasses
Bluetooth status, and completed a 15-second quiet window with zero unsolicited
image payload/error callbacks and zero audio payload/error/active-state
callbacks. Clean disconnect and Hi Rokid recovery passed.

Test 20 r3.2 implements the separately governed one-shot photo stage. It
uses one explicit operator-controlled `takePhoto(1920, 1080, 80)` request after
the accepted connection and service-status gates. Callback bytes are inspected
in memory for non-empty encoded-image metadata and a private digest, are never
written or previewed, and are followed by a bounded duplicate-callback window.
The argument semantics remain a working hypothesis; a pass qualifies only this
exact triplet and one callback lifecycle.

Test 20 r3.2.1.3 subsequently proves the synchronized two-phase host-tokenized one-shot photo gate: zero requests before arm, zero before the operator tap, exactly one accepted request afterward, no audio operation, and successful Hi Rokid recovery.
Test 20 r3.3 closes the remaining image-callback boundary. A strong callback retained and registered only before connection still timed out with the service stable; re-registering the same retained callback after successful connection/service-status qualification delivered one image payload callback with the unchanged `takePhoto(1920,1080,80)` request.
The accepted implementation rule for the tested firmware/Hi Rokid/`client-l:1.0.1` environment is therefore strong callback retention plus mandatory post-service-status re-registration before photo readiness. This is a behavioral qualification and does not prove the SDK internal mechanism. Audio streaming, direct/no-Hi-Rokid camera capture, and generalized third-argument semantics remain unqualified.
`TEST20_FINAL_STATUS=ACCEPTED_CLOSED_IMPLEMENTATION_RULE_PUBLISHED`

## Evidence
- [Test 20 r3.2.1.3 two-phase one-shot qualification](../tests/test-20-r3-2-1-3-two-phase-one-shot-photo-qualification.md)
- [Test 20 r3.3 callback non-delivery closure](../tests/test-20-r3-3-post-takephoto-image-callback-closure.md)
- [Test 20 final photo publication](../tests/test-20-final-photo-control-callback-publication.md)
- [Published final photo/callback summary](../research/connection-protocol/publication/test20-final-cxr-l-one-shot-photo-and-callback-closure.md)

- [Project status](../project-status.md)
- [Test 20 r1 census guide](../tests/test-20-r1-cxr-l-capability-census.md)
- [Test 20 r1.1 classification repair](../tests/test-20-r1-1-cxr-l-classification-repair.md)
- [Test 20 r1.2 final publication](../tests/test-20-r1-2-cxr-l-final-publication.md)
- [Test 20 r2 event qualification](../tests/test-20-r2-cxr-l-event-control-plane-qualification.md)
- [Test 20 r2.1 apply repair](../tests/test-20-r2-1-public-artifact-rollback-repair.md)
- [Test 20 r2.2 final callback publication](../tests/test-20-r2-2-final-ai-assist-callback-publication.md)
- [Published capability census](../research/connection-protocol/publication/test20-r1-cxr-l-capability-census.md)
- [Published AI-assist callback summary](../research/connection-protocol/publication/test20-r2-cxr-l-event-summary.md)
- [Test 20 r3 feasibility guide](../tests/test-20-r3-cxr-l-media-plane-feasibility.md)
- [Test 20 r3.0.1 publication closure](../tests/test-20-r3-0-1-final-media-plane-feasibility-publication.md)
- [Published media-plane feasibility census](../research/connection-protocol/publication/test20-r3-cxr-l-media-plane-feasibility.md)
- [Test 20 r3.1 no-payload preflight](../tests/test-20-r3-1-cxr-l-media-service-no-payload-preflight.md)
- [Published no-payload preflight summary](../research/connection-protocol/publication/test20-r3-1-cxr-l-no-payload-preflight.md)
- [Test 20 r3.1.1 publication closure](../tests/test-20-r3-1-1-final-no-payload-preflight-publication.md)
- [Test 20 r3.2 one-shot photo qualification](../tests/test-20-r3-2-cxr-l-one-shot-photo-qualification.md)
- [Connection-protocol research](../research/connection-protocol/README.md)
- [Boot-chain research](../research/boot-chain/README.md)

<!-- r27.1.2-status -->
### R27.1.2 repository consolidation status

The Test 21 sanitized-evidence packaging family is represented by one canonical engine plus thirty revision profiles. The final accepted r3.3.4.2.6.1.3 privacy policy, including dotted-version-safe IPv4 detection, is part of the shared implementation. Historical packager files remain untouched pending later retirement gates. New device testing remains paused during R27 consolidation.

<!-- r27.1.3-status -->
### R27.1.3 repository consolidation status

The current tree contains 32 historical source-contract checker files. Twenty-nine currently applicable Test 21 contracts are source-locked behind the canonical `rokid-research contract check` interface with exact legacy return-code/stdout equivalence. Three Test 20 contracts remain explicit deferred historical contracts because their predicates target superseded Test 20 source snapshots or require revision-specific output behavior. Historical checker deletion and rewrite remain `NONE`; new device testing remains paused during R27 consolidation.

<!-- r27.1.4-status -->
### R27.1.4 repository consolidation status

The historical Tests 19–21 `test_*_tools.py` family is represented by one source-locked canonical registry and `rokid-research test run` command. Thirty-eight current suites are qualified behind canonical dispatch. One Test 21 suite remains explicitly deferred because its required synthetic obfuscated AAR fixture is absent. Historical test rewrite/deletion remains `NONE`; new device testing remains paused during R27 consolidation.

### R27.1.5 repository consolidation status

The canonical tooling layer now shares one host-only primitive library for hashing/source locks, subprocess execution, syntax checks, marker/regex gates, sidecar generation, and privacy detection. A retirement-readiness gate identifies 42 independently implemented canonical retirement candidates (12 r25 validators and 30 Test 21 packagers), while the source-contract and tool-test families remain non-retireable because canonical dispatch still executes their historical oracle files. Historical file action and repository deletion remain `NONE`; new device testing remains paused during R27 consolidation.

### R27.1.12 repository consolidation status

The Tests 19–21 tool-test family is finalized as independent regression-oracle coverage rather than implementation duplication. Thirty-eight current suites remain byte-preserved and source-locked, execute through `rokid-research test run`, and must retain their expected passing test counts. One Test 21 suite remains deferred because its synthetic obfuscated-AAR fixture is absent. The R27.1 retirement queue is closed: 71 compatibility shims, 38 preserved regression oracles, four preserved historical/deferred entries, zero retirement candidates, zero inbound/container/source-lock blockers, and no repository path deletion. New device testing remains paused until the broader R27 whole-repository consolidation moves beyond the Tests 19–21/r25 families.


### R27.2.1 repository consolidation status

The post-R27.1 residual-host triage selected thirteen tracked r25 connection-protocol scripts for the next host-only consolidation slice: seven private-evidence finalizers and six sanitized-publication verifiers. R27.2.1 adds independent canonical engines and revision profiles for those behaviors and requires 7/7 finalizer plus 6/6 publication-verifier equivalence before any historical implementation reduction. The thirteen historical files remain byte-unchanged; repository deletion, device operation, and privileged operation remain `NONE`. New device testing remains paused during R27 consolidation.

### R27.2.2 repository consolidation status

The thirteen r25 finalization/publication implementations qualified by R27.2.1 are now preservation-backed compatibility shims: seven finalizers and six sanitized-publication verifiers. Existing runner/test call paths remain unchanged, while the active logic is centralized in the canonical engines. R27 canonicalized implementation count advances from 71 to 84. Repository path deletion, device operation, and privileged operation remain `NONE`.

## R27.2.8 FINAL

Repository/tooling consolidation is complete. The final machine gate is `scripts/rokid-research consolidation status`; expected state is `R27_WHOLE_HISTORY_CONSOLIDATION=COMPLETE` and `NEXT_DEVICE_TEST_READY=YES`. Next planned device research: Test 22 independent on-glasses Wi-Fi/routed-IP/direct-socket capability.

<!-- r27.3-final-publication -->
## R27 publication closure and next device gate

R27 whole-history consolidation is complete and R27.3 is the publication gate for that state. The accepted closure is 88 canonicalized historical implementations, 38 preserved independent regression oracles, four preserved historical/deferred entries, four explicitly preserved distinct implementation families, zero remaining host-only multi-member consolidation candidates, and zero source-lock failures. After R27.3 is merged and post-merge verification passes on `main`, the repository is ready for **Test 22 — Independent On-Glasses Wi-Fi, Routed IP, and Third-Party Direct Socket Capability**.
