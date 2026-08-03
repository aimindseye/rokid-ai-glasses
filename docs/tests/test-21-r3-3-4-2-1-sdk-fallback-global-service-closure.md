# Test 21 r3.3.4.2.1 — SDK-vs-Fallback Path Disambiguation, ExternalAppClient Reachability, Global-Package Intent Resolution, and IMediaStreamService Service-Side Corroboration

## Scope
Offline-only follow-up to accepted r3.3.4.2. No device, ADB, Bluetooth, network capture, Hi Rokid force-stop, CXR-L connection, photo, or audio operation occurs.

## Inputs
- Exact r3.3.4.2 repository overlay identities.
- Private APK set preserved by r3.3.4.1 (`raw/apks`), including all pulled split APKs.
- Optional exact `com.rokid.cxr:client-l:1.0.1` AAR if still in the local Gradle cache; no download is performed.
- Local `CxrLPhotoController` source, if present, as lexical corroboration only.

## Questions
1. Is `bindServiceFallback()` directly reachable from `invokeSdkConnect()`, and does source structure corroborate an error/conditional fallback role?
2. Is bundled `ExternalAppClient.a(String)` statically reachable from the custom CXR-L SDK root when virtual/interface dispatch is expanded?
3. Does the installed global Hi Rokid manifest declare `CXRLinkService`, and does the known `MEDIA_STREAM_SERVICE` action resolve to that service?
4. Does analysis of **all** preserved Hi Rokid APK splits recover `CXRLinkService.onBind()` and an `IMediaStreamService.Stub` implementation/lineage?

## Proof boundaries
- Static reachability is not a runtime call stack.
- Lexical Java/Kotlin source classification is corroboration, not compiler-level control-flow proof.
- Manifest intent-filter mapping proves package/component resolution metadata, not that a particular client Intent was issued at runtime.
- `IMediaStreamService` client `Stub.asInterface()` proof remains separate from service-side `onBind()` corroboration.
