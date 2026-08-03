# Test 21 r3.3.4.2 — CXR-L→CXRLinkService static contract closure

## Purpose
Recover the static Java/Dalvik contract that r3.3.4.1 could not expose dynamically: the CXR-L call path to `Context.bindService`, Intent construction, `ServiceConnection.onServiceConnected`, `Stub.asInterface(IBinder)`, and the service-side Binder/AIDL lineage.

## Inputs
- Accepted r3.3.4.1 repository files (exact-hash prerequisite).
- The private APK copies already pulled by r3.3.4.1 under its evidence root (`raw/apks`).
- Optional exact `com.rokid.cxr:client-l:1.0.1` AAR. Expected SHA-256: `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`. The analyzer automatically searches the normal Gradle cache; merged custom-APK bytecode remains the primary call-path source if the AAR cache entry is absent.

## Method
The analyzer is self-contained and does not require JADX. It parses DEX tables, class definitions, method code, invoke instructions, constants, fields, class/interface lineage and a bounded register-state model. It identifies `bindService` call sites, reconstructs directly observable Intent fields, follows a shortest static caller chain from the custom package, identifies classes implementing `android.content.ServiceConnection`, resolves `onServiceConnected` calls to generated `Stub.asInterface(IBinder)`, and cross-checks the Hi Rokid `CXRLinkService.onBind`/Stub hierarchy.

## Proof levels
- `BIND_SERVICE_CALLSITE_PROVEN`: a bytecode invoke of Android `bindService` exists.
- `CUSTOM_TO_BIND_CALL_PATH_PROVEN`: a static invoke path from the custom package reaches that site.
- Intent fields are exact only when reconstructed from bytecode constants/setters/factories.
- `SERVICECONNECTION_ASINTERFACE_PROVEN`: `onServiceConnected` invokes a generated `$Stub.asInterface`.
- `BINDER_INTERFACE_DESCRIPTOR` is exact only when client `asInterface` lineage and/or service Stub lineage identifies one descriptor.
- `STATIC_DEPENDENCY_CLOSURE_EXACT=YES` requires bind call + recovered Intent contract + ServiceConnection/asInterface + exact Binder descriptor.

No method bodies, APKs, raw DEX, tokens, device identifiers or proprietary bytecode are included in the sanitized ZIP.

## Safety
Offline existing-evidence analysis only. No ADB, no package mutation, no capture, no force-stop, no authorization, no connection attempt, no photo/audio operation.
