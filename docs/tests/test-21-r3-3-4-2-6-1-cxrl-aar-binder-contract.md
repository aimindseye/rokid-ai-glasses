# Test 21 r3.3.4.2.6.1 — Exact CXR-L AAR Stub/Proxy Transaction Recovery

## Purpose

Recover the exact Binder ABI exposed by `com.rokid.cxr:client-l:1.0.1` from the already-qualified local AAR and close as much of the clean-room compatibility boundary as the SDK artifact itself proves.

This phase reconstructs:

- the exact 33-method `IMediaStreamService` interface surface;
- `Stub.TRANSACTION_*` integer constants;
- `Stub.onTransact()` code-to-method dispatch;
- `Stub.Proxy` `IBinder.transact()` codes;
- ordered `Parcel` read/write calls visible in each Proxy method;
- CXR-L wrapper methods that invoke the Binder interface;
- nearest public CXR-L methods that lead to those direct Binder calls.

## Access and safety boundary

No phone access is required.

No trusted/root access is required. The runner does not invoke ADB, Magisk/Superuser, Frida, `/proc`, ptrace, signals, application lifecycle commands, or any device command. It also performs no network operation. It reads only a local AAR from the host filesystem.

The real-run AAR is accepted only when its SHA-256 is exactly:

`c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`

for Maven coordinate:

`com.rokid.cxr:client-l:1.0.1`

The analyzer searches the local Gradle and Maven caches. An explicit `--aar` path may also be supplied. It never downloads an artifact automatically.

## Exactness gates

A clean-room transaction contract is considered ready only when:

1. the exact known 33-method signature set is present;
2. the expected Binder descriptor is present;
3. both Stub and Proxy classes are present;
4. all 33 transaction codes are uniquely reconstructed;
5. at least two independent representations agree for every method;
6. no transaction-source mismatch exists;
7. either Proxy or onTransact coverage is complete for all 33 methods; and
8. all 33 Proxy methods expose a recoverable Parcel contract with interface-token and reply-exception handling.

A lone `TRANSACTION_*` constant is therefore not enough to claim exact closure.

## What this does not prove

This phase does not recover Hi Rokid authorization, session lifecycle, timing, reconnect behavior, cloud policy, device ownership rules, callback semantics beyond the Binder ABI, or any proprietary service implementation. `FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN` and `SERVICE_IMPLEMENTATION_RECOVERED` remain `NO` by design.

## Sanitized publication boundary

The sanitized summary may contain API names, method descriptors, transaction numbers, Parcel-operation names, and CXR-L wrapper call relationships. It excludes the AAR, class bytes, local paths, tokens, serials, packet captures, and any phone-derived private artifact.
