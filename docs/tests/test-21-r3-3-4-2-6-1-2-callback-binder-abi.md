# Test 21 r3.3.4.2.6.1.2 — Exact Callback Binder ABI Recovery

## Purpose

This phase completes the static IPC boundary needed for a future clean-room compatibility scaffold by recovering the Binder ABI for the seven callback Binder interfaces referenced by the accepted `IMediaStreamService` contract:

- `IImageStreamCallback`
- `IAudioStreamCallback`
- `ICustomViewCallback`
- `IDeviceStatusCallback`
- `ICustomCmdCallback`
- `IGlassAppCallback`
- `IAiEventCallback`

The input remains the exact locally cached CXR-L AAR `com.rokid.cxr:client-l:1.0.1` with SHA-256 `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`.

## Safety and access boundary

No phone access is required. No trusted/root access is required. This test performs no ADB, Magisk, Frida, ptrace, process-memory, device-control, photo, audio, or network operation. It reads only an already-local AAR on the host.

## Recovery method

For each of the seven callback Binder interfaces the analyzer:

1. enumerates the interface method surface from `classes.jar`;
2. identifies the Binder Stub, preferring the literal `$Stub` and allowing a unique structural Binder/onTransact fallback;
3. structurally identifies the client-side Proxy without requiring a literal `$Proxy` class name;
4. derives transaction IDs independently from Stub `onTransact()` and Proxy `IBinder.transact(...)`;
5. requires exact two-source agreement with zero mismatches for every callback method;
6. records ordered request/reply Parcel operations;
7. explicitly distinguishes synchronous reply transactions from one-way callback transactions (`transact` flag 1 with no reply Parcel);
8. declares an interface ABI ready only when descriptor, Stub, Proxy, transaction and Parcel gates all close.

## Evidence gates

`ALL_CALLBACK_BINDER_ABIS_READY=YES` requires all seven interfaces to pass their own exact ABI gate. `CLEAN_ROOM_FULL_BINDER_BOUNDARY_READY=YES` additionally requires the complete callback aggregate to have zero transaction mismatches and complete Parcel contracts.

A positive result closes the static service/callback Binder boundary together with accepted r3.3.4.2.6.1.1. It does not recover Hi Rokid authorization, lifecycle/session timing, cloud behavior, business semantics, or proprietary service implementation, and it does not claim functional compatibility.

## Outputs

The sanitized package contains only:

- aggregate text/JSON/Markdown summaries;
- per-interface closure summary;
- callback transaction map;
- callback Parcel-marshalling table.

No local AAR path, device identifier, token, device data, raw runtime memory, media, or network material is included.
