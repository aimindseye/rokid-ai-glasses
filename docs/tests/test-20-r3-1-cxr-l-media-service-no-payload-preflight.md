# Test 20 r3.1 — CXR-L Media Service Status and No-Payload Preflight Qualification

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-08-01 -->

## Purpose

Test 20 r3.1 is the bounded runtime safety gate after the accepted r3.0.1 static
media-plane census. It performs one CXR-L `CUSTOMAPP` connection, registers the
public image and audio callback interfaces, queries service version, service
version code, and glasses Bluetooth status, then observes a 15-second quiet
window.

## Explicitly prohibited

The app does not invoke `takePhoto()`, `startAudioStream()`, or
`stopAudioStream()`. It does not retain image or audio payloads, request cloud
services, use custom commands/views, manage glass apps, or access the exported
provider. The final merged APK must not contain Internet, Camera, or Record
Audio permission.

## Pass boundary

A passing run requires one authorization and connection attempt; successful
callback registration; successful service version, version-code, and Bluetooth
status queries; zero image payload/error callbacks; zero audio payload/error or
active-stream callbacks; clean disconnect; and Hi Rokid recovery.

An audio state callback reporting `false` may be recorded without failure. A
state callback reporting `true`, any payload callback, or any error callback is
terminal failure because no media operation was requested.

## Runtime-qualified delta

A passing run may qualify only these client-level methods in this bounded use:

- `setCXRImageCbk(IImageStreamCbk): void`
- `setCXRAudioCbk(IAudioStreamCbk): void`
- `getServiceVersion(): String`
- `getServiceVersionCode(): Integer`
- `isGlassBtConnected(): boolean`

It does not qualify `takePhoto()`, `startAudioStream()`, `stopAudioStream()`,
payload formats, parameter semantics, direct binder methods, or media capture.

## Baseline

- repository source: `dfa7693ab40fd5a76456b57d0e0222646afc5cb3`
- glasses firmware: `1.23.009-20260725-153201`
- Hi Rokid: `G1.11.11.0727`
- SDK: `com.rokid.cxr:client-l:1.0.1`


## Accepted physical result

Test 20 r3.1 completed one governed physical attempt on firmware
`1.23.009-20260725-153201` with Hi Rokid `G1.11.11.0727` and
`com.rokid.cxr:client-l:1.0.1`.

- callback registration: PASS
- service version: present; public value represented only by SHA-256
- service version code: `10000`
- glasses Bluetooth status: connected
- quiet observation window: `15000` ms
- image payload/error callbacks: `0` / `0`
- audio payload/error/active-state callbacks: `0` / `0` / `0`
- clean disconnect: PASS
- Hi Rokid recovery: PASS
- terminal: `NO_PAYLOAD_OBSERVATION_COMPLETE`

No photo request, audio-stream request, payload retention, or cloud request was
performed. The runtime-qualified delta is limited to the five methods listed
above. `takePhoto()`, `startAudioStream()`, `stopAudioStream()`, payload formats,
parameter semantics, and media transport behavior remain unqualified.

## Publication

- [Machine-readable accepted summary](../research/connection-protocol/publication/test20-r3-1-cxr-l-no-payload-preflight.json)
- [Human-readable accepted summary](../research/connection-protocol/publication/test20-r3-1-cxr-l-no-payload-preflight.md)
- [Evidence identities](../research/connection-protocol/publication/test20-r3-1-cxr-l-evidence-hashes.txt)
- [Final r3.1.1 publication closure](test-20-r3-1-1-final-no-payload-preflight-publication.md)

## Next boundary

Test 20 r3.2 may design exactly one bounded `takePhoto()` invocation and one
image-callback observation path. It must remain a separate approval, build,
install, and physical-run workflow.
