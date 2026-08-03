# Test 21 r3.3.4.2.6.1.1 — Obfuscation-Resilient Binder Proxy Discovery and Two-Source Contract Closure

## Purpose

This phase repairs the two bounded limitations observed in r3.3.4.2.6.1 without touching the phone. It structurally identifies an obfuscated Binder Proxy even when the literal `IMediaStreamService$Stub$Proxy` class name was removed, reconstructs client-side transaction IDs and Parcel operation order, and repairs public SDK-wrapper reachability so that `ExternalAppClient`-style facades do not have to live in a `com.rokid.cxr` package.

No phone access is required. No trusted/root access is required. The test uses only the already-qualified local `com.rokid.cxr:client-l:1.0.1` AAR whose expected SHA-256 is fixed in source.

## Safety / access boundary

The runner and analyzer perform no ADB, root, Magisk, Frida, ptrace, `/proc` reads, process attachment, app launch/stop, glasses operation, photo/audio operation, or network download. If the exact AAR is not present in the local Gradle/Maven cache, the test stops and reports that condition.

## Proof strategy

The structural Proxy candidate must implement `IMediaStreamService`, contain actual `IBinder.transact` calls, and implement the exact 33-method surface. A unique highest-scoring exact candidate is required; ambiguity is not silently resolved by name.

For each Binder method the analyzer independently recovers:

1. the transaction code selected by `Stub.onTransact()`;
2. the numeric transaction code passed by the structurally identified Proxy to `IBinder.transact()`;
3. ordered request-side `Parcel.write*` operations before the transact;
4. ordered reply-side `Parcel.read*` operations after the transact.

Two-source transaction closure requires all 33 Stub mappings plus all 33 Proxy mappings, 33 exact agreements, zero mismatches, and 33 unique transaction IDs. Parcel closure separately requires request and reply contract evidence for all 33 methods.

## Wrapper reachability repair

The analyzer no longer treats `com.rokid.cxr/...` as the only possible public SDK namespace. A public class with direct Binder bridges to at least three distinct `IMediaStreamService` methods is classified as a structural Binder facade. Public-root reachability can terminate at that facade as well as at public `com.rokid.cxr` methods.

## Interpretation boundary

`CLEAN_ROOM_BINDER_ABI_READY=YES` means the static client Binder ABI is sufficiently closed for an independently implemented compatibility scaffold at the descriptor/signature/transaction/Parcel-marshalling layer.

It does not recover Hi Rokid authorization policy, session lifecycle, timing semantics, cloud behavior, proprietary algorithms, or the vendor service implementation. `FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN`, `AUTHORIZATION_SEMANTICS_RECOVERED`, `SESSION_LIFECYCLE_SEMANTICS_RECOVERED`, and `SERVICE_IMPLEMENTATION_RECOVERED` therefore remain `NO`.

## Private/public evidence

The local analysis JSON remains under the evidence directory. The shareable ZIP contains only the allow-listed sanitized summary, transaction table, exact Parcel-marshalling operation table, and wrapper bridge table. It contains no device identifiers, phone data, tokens, screenshots, media, PCAP, memory, or filesystem paths.
