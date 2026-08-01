# Test 20 Final — Photo Control, Callback Closure, and Canonical Implementation

## Purpose

This publication closes the governed one-shot CXR-L photo workstream without another physical photo experiment. It integrates the accepted r3.2.1.3 and r3.3 sanitized evidence and converts the successful r3.3 lifecycle into the canonical photo-controller implementation.

## Runtime-qualified boundary

For firmware `1.23.009-20260725-151201`, Hi Rokid `G1.11.11.0727`, and `com.rokid.cxr:client-l:1.0.1` (AAR SHA-256 `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`):

- the custom CXR-L session and service-status path is device-qualified;
- the two-phase host-tokenized one-shot photo arm is device-qualified;
- exactly one `takePhoto(1920,1080,80)` request was accepted in each accepted photo run;
- the image payload callback path is proven when the retained callback is re-registered after connection/service establishment;
- audio streaming was not invoked;
- image payloads are not published or retained by the publication workflow.

## Implementation repair

The canonical controller keeps a strong image callback reference, registers it before connect, and unconditionally re-registers the same object after successful service-status qualification. `photoReady` is not reached unless that post-connect registration succeeds. The r3.2.1.3 host arm and atomic one-shot gate remain mandatory. Diagnostic profile selection and the unused third-argument-zero branch are removed from the canonical implementation.

## Interpretation boundary

The evidence proves the successful lifecycle behavior, not why the SDK behaves that way internally. The third photo argument remains a working hypothesis rather than a generalized semantic claim. The result also does not qualify camera capture without Hi Rokid, audio streaming, or other firmware/SDK combinations.

## Publication

- [consolidated machine publication](../research/connection-protocol/publication/test20-final-cxr-l-one-shot-photo-and-callback-closure.json)
- [human-readable publication](../research/connection-protocol/publication/test20-final-cxr-l-one-shot-photo-and-callback-closure.md)
- [evidence identities](../research/connection-protocol/publication/test20-final-evidence-hashes.txt)
- [publication schema](../research/connection-protocol/publication/test20-final-cxr-l-one-shot-photo-and-callback-closure.schema.json)

`TEST20_FINAL_STATUS=ACCEPTED_CLOSED_IMPLEMENTATION_RULE_PUBLISHED`
