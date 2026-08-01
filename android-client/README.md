# Android Client Experiments

The historical `app` module contains the RFCOMM channel probe. The historical
`test19` CXR-M module and evidence remain for research traceability, but its
monolithic runner is disabled.

## Test 19 r2 CXR-L module

The `test19r2` module resolves exactly `com.rokid.cxr:client-l:1.0.1`, requests
authorization through Hi Rokid, configures one `CUSTOMAPP` session, waits for
`onCXRLConnected(true)` and `onGlassBtConnected(true)`, and disconnects. It
contains no media, APK upload, reboot, unpair, or Hi Rokid force-stop action.

Build through `scripts/tests/prepare_test19_r2.sh`; do not invoke Gradle without
the exact `-ProkidCxrLVersion=1.0.1` property. See the
[Test 19 r2 runbook](../docs/developer/companion-app/test-19-r2-qualification.md).

## Test 20 r2 safe event observer

The `test20r2` module reuses the qualified CXR-L authorization and `CUSTOMAPP`
connection lifecycle but does not invoke an AI assistant, camera, microphone,
media stream, custom command, custom view, app-management operation, or cloud
client. It passively observes exactly two ordered
`onGlassAiAssistStart()`/`onGlassAiAssistStop()` cycles generated through the
ordinary stock glasses interaction, then disconnects.

Build, install, and run only through the governed Test 20 r2 scripts. See the
[Test 20 r2 runbook](../docs/tests/test-20-r2-cxr-l-event-control-plane-qualification.md).

## Test 20 r3.1 media-service no-payload preflight

The `test20r31` module reuses the qualified CXR-L authorization and `CUSTOMAPP`
connection lifecycle, registers the declared image and audio callback interfaces,
queries service version/version-code and glasses Bluetooth status, then observes a
bounded quiet window. It does not call `takePhoto()`, `startAudioStream()`,
`stopAudioStream()`, or any media-producing API. The merged APK removes Internet,
Camera, and Record Audio permissions.

Build, install, and run only through the governed Test 20 r3.1 scripts. See the
[Test 20 r3.1 runbook](../docs/tests/test-20-r3-1-cxr-l-media-service-no-payload-preflight.md).
