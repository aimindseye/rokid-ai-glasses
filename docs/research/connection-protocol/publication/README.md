# Connection-Protocol Publications

Machine-readable files in this directory describe accepted sanitized research
boundaries. Private evidence bytes, credentials, authorization-token values,
device serials, raw Bluetooth addresses, and media payloads are excluded.

## Test 19 r2.4.1 CXR-L publication closure

- [Firmware comparison JSON](test19-r2-cxr-l-firmware-comparison.json)
- [Public evidence hashes](test19-r2-cxr-l-evidence-hashes.txt)
- [Developer-facing final findings](../../../developer/companion-app/test-19-r2-final-findings.md)

The publication records the accepted firmware comparison and the r2.4
repair-only physical smoke closure.

## Test 20 r1.2 final corrected capability census

- [Machine-readable corrected census](test20-r1-cxr-l-capability-census.json)
- [Human-readable corrected census](test20-r1-cxr-l-capability-census.md)
- [Evidence identities](test20-r1-cxr-l-evidence-hashes.txt)
- [Publication schema](test20-r1-cxr-l-capability-census.schema.json)
- [Final publication closure](../../../tests/test-20-r1-2-cxr-l-final-publication.md)

Test 20 r1.2 publishes the reviewed r1.1 repair. Runtime qualification is
restricted to nine descriptor-exact members and two Hi Rokid components. The
first r1 sanitized output remains withdrawn because it propagated class-level
participation to unrelated members.

The corrected census is a selection boundary, not permission to invoke every
listed surface. At r1.2, camera, audio, AI-assist callbacks, custom commands,
custom views, glass-app operations, provider access, and native/JNI behavior
remained untested. Test 20 r2.2 separately qualifies only the two AI-assist
start/stop callbacks without rewriting the immutable r1.2 census.

## Test 20 r2.2 AI-assist callback qualification

- [Machine-readable event summary](test20-r2-cxr-l-event-summary.json)
- [Human-readable event summary](test20-r2-cxr-l-event-summary.md)
- [Event-summary schema](test20-r2-cxr-l-event-summary.schema.json)
- [Evidence identities](test20-r2-cxr-l-evidence-hashes.txt)
- [Final publication closure](../../../tests/test-20-r2-2-final-ai-assist-callback-publication.md)

The accepted run observed two ordered `onGlassAiAssistStart()`/
`onGlassAiAssistStop()` cycles with zero duplicate starts and zero
out-of-order stops, followed by clean disconnect and Hi Rokid recovery.
The test app made no assistant invocation, cloud AI request, camera,
microphone, media-stream, custom-command, custom-view, provider, or
glass-app-management operation.


## Test 20 r3.0.1 media-plane feasibility census

- [Machine-readable feasibility census](test20-r3-cxr-l-media-plane-feasibility.json)
- [Human-readable feasibility census](test20-r3-cxr-l-media-plane-feasibility.md)
- [Publication schema](test20-r3-cxr-l-media-plane-feasibility.schema.json)
- [Evidence identities](test20-r3-cxr-l-evidence-hashes.txt)
- [Final publication closure](../../../tests/test-20-r3-0-1-final-media-plane-feasibility-publication.md)

The accepted read-only census contains 23 stable declared public surfaces:
eight client entry points, five callbacks, and ten media-service contract
members. It confirms static image/audio control, callback, and service paths.
No media API was invoked, no media payload was collected, parameter semantics
and payload formats remain unresolved, and runtime qualification was not
granted.

## Test 20 r3.1.1 no-payload media-service preflight

- [Machine-readable preflight summary](test20-r3-1-cxr-l-no-payload-preflight.json)
- [Human-readable preflight summary](test20-r3-1-cxr-l-no-payload-preflight.md)
- [Publication schema](test20-r3-1-cxr-l-no-payload-preflight.schema.json)
- [Evidence identities](test20-r3-1-cxr-l-evidence-hashes.txt)
- [Final publication closure](../../../tests/test-20-r3-1-1-final-no-payload-preflight-publication.md)

The accepted run registered image and audio callback interfaces, queried the
service version, service version code, and glasses Bluetooth status, and then
observed a 15-second quiet window. It received zero unsolicited image
payload/error callbacks and zero audio payload/error/active-state callbacks.
Clean disconnect and Hi Rokid recovery passed.

Runtime qualification is limited to `setCXRImageCbk(IImageStreamCbk)`,
`setCXRAudioCbk(IAudioStreamCbk)`, `getServiceVersion()`,
`getServiceVersionCode()`, and `isGlassBtConnected()`. The publication does not
qualify photo capture, audio streaming, payload formats, parameter semantics,
or media transport performance.
