# Test 21 r3.3.4.2.6 — Privilege-Free Binder Transaction Contract Reconstruction, Client-Call Census, and Clean-Room Replacement Boundary

## Purpose

Pivot away from the root/runtime-memory branch and extract the maximum defensible compatibility contract from artifacts that are already local from accepted Test 21 work.

No phone access is required. This test does not request root, Magisk/Superuser permission, Android Debug Bridge access, Frida, process memory, or any new device trust/authorization.

The objective is not to recover the proprietary `CXRLinkService` implementation. Instead, the test reconstructs the client-visible Binder interface needed for a clean-room replacement effort:

- exact Binder descriptor;
- exact interface method signatures;
- generated AIDL `TRANSACTION_*` integer mapping when present in merged client bytecode;
- independent generated Proxy `IBinder.transact(...)` code cross-check where statically recoverable;
- shortest static call paths from the custom companion into each Binder method;
- the subset of Binder methods actually reachable from the custom companion;
- API type inventory for arguments and return values;
- an explicit clean-room readiness gate that distinguishes interface compatibility from functional behavior compatibility.

## Inputs

- The accepted r3.3.4.2 repository files, checked by exact SHA-256 identity.
- The existing r3.3.4.1 private evidence root containing the already-pulled custom companion APK under `raw/apks`.

No new APK pull is performed. No device connection is required during this test.

## Proof rules

`TRANSACTION_MAP_COMPLETE=YES` requires all recovered interface methods to have exactly one unique `TRANSACTION_<method>` integer and no extra or duplicate transaction assignments.

`PROXY_TRANSACTION_MISMATCH_COUNT=0` means every statically observable Proxy transaction code agrees with the generated Stub transaction field. A missing Proxy observation does not fabricate a mismatch; it simply contributes no independent confirmation.

`CLEAN_ROOM_INTERFACE_SCAFFOLD_READY=YES` requires all of the following:

1. exact descriptor `com.rokid.sprite.aiapp.externalapp.IMediaStreamService`;
2. exact accepted interface method count of 33;
3. complete unique transaction map;
4. no observed Proxy/Stub transaction-code mismatch.

This gate means an interface-level scaffold can be designed from public client-visible facts. It does **not** mean functional behavior, timing, callback semantics, authorization semantics, Bluetooth/media behavior, or service implementation logic has been recovered.

`FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN` remains `NO` in this deliverable by design.

`SERVICE_IMPLEMENTATION_RECOVERED` remains `NO` in this deliverable by design.

## Privacy boundary

The private result may contain static call paths and the SHA-256 of the already-local custom APK. It does not copy the APK or raw bytecode.

The sanitized summary contains only API symbols/signatures, transaction codes, bounded counts, compatibility gates, and a transaction-map TSV. It excludes:

- APK/DEX payloads;
- process memory/maps;
- device serials;
- authentication tokens;
- photos/audio;
- packet captures or TLS key logs.

## Device and mutation boundary

- Root: none.
- Magisk/Superuser authorization: none.
- ADB: none.
- Frida: none.
- `/proc/<pid>/mem`: none.
- Process attach/signals: none.
- Package install/launch/force-stop: none.
- CXR-L connection attempt: none.
- Photo/audio operation: none.
- Network capture: none.
- Repository mutation: additive overlay only.

## Interpretation

This is the preferred next branch when the research goal is to keep the personal phone and personal glasses out of privileged runtime instrumentation. It trades implementation recovery for a clean-room, client-contract-first path that can later support a replacement-service prototype without claiming proprietary behavior that has not been observed or independently specified.
