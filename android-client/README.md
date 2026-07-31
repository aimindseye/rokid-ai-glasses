# Android Client Experiments

The existing `app` module contains the historical channel probe. The `test19`
module is a separate CXR-M connection-only qualification client.

## Test 19 r1 module

The module resolves `com.rokid.cxr:client-m:<version>` from Rokid's Maven
repository. Supply the exact version selected by the committed resolver:

```bash
./gradlew :test19:assembleDebug -ProkidCxrVersion='<VERSION>'
```

The app dynamically attests the CXR API surface, discovers devices advertising
service UUID `00009100-0000-1000-8000-00805f9b34fb`, invokes the documented
initial Bluetooth connection path, queries allowlisted status methods, and
calls `deinitBluetooth()`.

Network and Wi-Fi permissions are present because the documented SDK requires
them. The test's privacy boundary is enforced by capture-based destination
analysis, not by deleting required Android permissions. No proprietary SDK
artifact is committed.

See the [Test 19 r1 runbook](../docs/developer/companion-app/test-19-r1-qualification.md).
