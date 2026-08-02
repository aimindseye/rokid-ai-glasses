# Test 21 — Static Binder Boundary Overview

## Executive summary

Test 21 closes the **static clean-room Binder boundary** for the analyzed Rokid client artifact `com.rokid.cxr:client-l:1.0.1`.

The closure combines two independent halves:

1. **Service-side/client Binder ABI closure** from `r3.3.4.2.6.1.1`.
2. **Callback-side Binder ABI closure** completed by `r3.3.4.2.6.1.3`, building on the callback Proxy/Parcel baseline from `r3.3.4.2.6.1.2`.

Final accepted callback-side closure metrics are:

- callback interfaces: **7/7**;
- callback methods: **21/21**;
- host Stub dispatch confirmations: **21/21**;
- previously missing confirmations recovered: **7/7**;
- Stub ↔ Proxy mismatches: **0**;
- Parcel contracts: **21/21**;
- callback interfaces ABI-ready: **7/7**;
- `CLEAN_ROOM_FULL_BINDER_BOUNDARY_READY=YES`.

## What was actually proven

The work proves that the client-side Binder contract can be described statically with exact transaction-code and Parcel-marshalling detail for the accepted client artifact.

That means a clean-room implementer can understand:

- which service-side transactions exist and how the client marshals them;
- which callback interfaces exist and how the service calls back into the client;
- the exact transaction code used per callback method;
- the argument and reply Parcel contracts for each callback transaction;
- which callback methods were confirmed directly from real compiled `Stub.onTransact(...)` behavior.

## What was not proven

A PASS does **not** prove:

- end-to-end functional behavior compatibility;
- authorization semantics;
- session lifecycle semantics;
- proprietary service-side implementation behavior;
- cloud behavior or backend dependencies.

Literal non-claims preserved by the accepted result:

- `FUNCTIONAL_BEHAVIOR_COMPATIBILITY_PROVEN=NO`
- `AUTHORIZATION_SEMANTICS_RECOVERED=NO`
- `SESSION_LIFECYCLE_SEMANTICS_RECOVERED=NO`
- `SERVICE_IMPLEMENTATION_RECOVERED=NO`

These limits must remain explicit in any publication or PR summary.

## Accepted identities

- AAR coordinate: `com.rokid.cxr:client-l:1.0.1`
- AAR SHA-256: `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`
- `classes.jar` SHA-256: `d2e1e2c875eb0283b80dd053b5edfcabd97b351d2c83abbcaa7026317f0b39d3`
- callback baseline source ZIP SHA-256 (`r3.3.4.2.6.1.2`): `366facf0b4e87e6f100c0a0c322cdf298a98d7a82a8f782add2b716f4cf2fa8b`

## Host-only policy

This workstream remained host-only and non-privileged throughout publication-ready recovery:

- `ROOT_REQUIRED=NO`
- `MAGISK_REQUIRED=NO`
- `ADB_REQUIRED=NO`
- `FRIDA_REQUIRED=NO`
- `PHONE_ACTION=NONE`
- `DEVICE_OPERATION=NONE`
- `PHOTO_OPERATION=NONE`
- `AUDIO_OPERATION=NONE`
- `NETWORK_CAPTURE=NONE`

## Reader map

- See [Test 21 — Findings](./test21-static-binder-boundary-findings.md) for the detailed conclusions.
- See [Test 21 — Diagrams](./test21-static-binder-boundary-diagrams.md) for the visual explanation.
- See [Test 21 — Callback Transaction Reference](./test21-callback-transaction-reference.md) for the method-by-method callback map.
- See [Test 21 — Publication Checklist](./test21-publication-checklist.md) for PR/release guidance.
