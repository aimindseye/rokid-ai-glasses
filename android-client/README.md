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
