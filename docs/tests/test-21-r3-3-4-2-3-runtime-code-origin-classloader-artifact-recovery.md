# Test 21 r3.3.4.2.3 — CXRLinkService Runtime Code-Origin Closure

## Scope

Read-only follow-up to accepted r3.3.4.2.2. The client-side fallback contract is already closed. This test asks only where the installed/runtime Hi Rokid process obtains the executable definitions for `CXRLinkService` and the `IMediaStreamService` service-side implementation.

## Collection

The harness uses ADB only for reads: `pm path`, `dumpsys package`, package shared-library listing, `pidof`, optional `/proc/<pid>/maps`, `dumpsys meminfo`, and `adb pull` of PackageManager-reported or narrowly discovered APK/JAR/DEX code containers. It never starts, stops, clears, installs, disables, enables, authorizes, connects, photographs, records audio, or changes Bluetooth state.

`/proc/<pid>/maps` is opportunistic. Android permission denial is a bounded blocker, not evidence that no dynamic code exists.

## Closure rules

`CXRLINKSERVICE_CODE_ORIGIN_CLOSURE=YES` requires an exact `class_def` for `Lcom/rokid/sprite/aiapp/externalapp/service/CXRLinkService;` in a read-only pulled artifact. Raw descriptor/string references are not sufficient.

Binder-side classes (`IMediaStreamService`, `$Stub`, `$Stub$Proxy`) are reported independently. Service `onBind` presence is also independent; no stub lineage is inferred from names alone.

All remote install paths, process maps, dumpsys output, pulled APK/JAR/DEX files and process IDs stay private. Sanitized output contains bounded origin IDs, basenames, hashes, counts and dispositions only.
