# Test 21 r3.3.4.2.6.1.3 — Obfuscation-Resilient Callback Stub Dispatch Recovery

## Purpose

Close the seven callback transactions left without independent Stub-side confirmation by r3.3.4.2.6.1.2, without repeating Proxy/Parcel recovery and without using a phone or privileged runtime instrumentation.

## Accepted inputs

- r3.3.4.2.6.1.2 sanitized-summary ZIP SHA-256:
  `366facf0b4e87e6f100c0a0c322cdf298a98d7a82a8f782add2b716f4cf2fa8b`
- `com.rokid.cxr:client-l:1.0.1` AAR SHA-256:
  `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`
- `classes.jar` SHA-256:
  `d2e1e2c875eb0283b80dd053b5edfcabd97b351d2c83abbcaa7026317f0b39d3`
- service-side prerequisite:
  `r3.3.4.2.6.1.1_ACCEPTED_TWO_SOURCE_CLIENT_BINDER_ABI`

## Recovery method

The analyzer builds minimal clean-room `android.os` stand-ins on the host, compiles one concrete callback implementation for each of the seven exact callback Stubs, and invokes each compiled Stub's real `onTransact` implementation for every callback transaction code present in the accepted Proxy map.

This method is resilient to renamed nested classes, switch lowering, branch layout, and bytecode-owner differences because it does not infer dispatch from decompiler formatting or opcode-neighborhood heuristics. The observed callback method reached by `onTransact(code, ...)` is compared with the independently recovered Proxy mapping from r3.3.4.2.6.1.2.

No proprietary AAR/JAR bytecode is copied into the sanitized output.

## Closure gate

A production result may claim full static Binder boundary closure only when all of the following hold:

- callback interfaces: 7/7;
- callback methods: 21/21;
- host Stub dispatch confirmations: 21/21;
- seven formerly missing confirmations: 7/7;
- Stub ↔ Proxy transaction mismatches: 0;
- request Parcel contracts: 21/21;
- reply Parcel contracts: 21/21;
- ABI-ready callback interfaces: 7/7;
- accepted r3.3.4.2.6.1.1 service Binder prerequisite present.

## Scope limits

Even a PASS does **not** prove authorization semantics, session lifecycle, proprietary Rokid service implementation, cloud behavior, or end-to-end functional compatibility.

## Device policy

`ROOT_REQUIRED=NO`, `MAGISK_REQUIRED=NO`, `ADB_REQUIRED=NO`, `FRIDA_REQUIRED=NO`, `PHONE_ACTION=NONE`, `DEVICE_OPERATION=NONE`, `PHOTO_OPERATION=NONE`, `AUDIO_OPERATION=NONE`, and `NETWORK_CAPTURE=NONE`.
