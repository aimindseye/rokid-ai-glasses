# Test 20 r3.3 — Post-`takePhoto` Image-Callback Non-Delivery Closure

## Purpose

r3.3 preserved the r3.2.1.3 two-phase one-shot gate and isolated why an accepted `takePhoto(1920,1080,80)` request produced no image callback.

## Profile 1 — `STRONG_REF_PRECONNECT`

The controller retained a strong `IImageStreamCbk` reference for the entire run and registered it before connection.

- prerequisite/armed/final gates: PASS
- resolved photo request count: `1`
- `takePhoto` returned: `true`
- image payload/error callbacks: `0` / `0`
- service classified stable through timeout
- classification: `REQUEST_ACCEPTED_NO_CALLBACK_SERVICE_STABLE`

This rules out a missing Java strong reference as a sufficient explanation.

## Profile 2 — `POSTCONNECT_REREGISTER`

The same retained callback object was registered again after connection/service-status qualification and before host arming. The photo request remained `takePhoto(1920,1080,80)`.

- prerequisite/armed/final gates: PASS
- resolved photo request count: `1`
- `takePhoto` returned: `true`
- callback dispatch count: `1`
- image payload/error callbacks: `1` / `0`
- terminal: `ONE_SHOT_PHOTO_RECEIVED`
- classification: `IMAGE_CALLBACK_DELIVERED`

The behavioral difference strongly implicates callback-registration timing or session establishment. It does not establish the SDK's internal mechanism.

## Profile 3

`ARG3_ZERO_DIAGNOSTIC` was not run. Callback delivery was already proven with the original third argument `80`, so changing that argument was no longer justified. Its semantics remain unresolved.

## Sanitized evidence

- `STRONG_REF_PRECONNECT` ZIP SHA-256: `96716c665f268f543686b7fcc9d2b8f87526c835d8a4994d21c908c1371b0ce5`
- `POSTCONNECT_REREGISTER` ZIP SHA-256: `dd8b8580e484968bdb75b20c6d00188d2b564efa1697b52e17f461bf3502b35c`
- [pre-connect machine summary](../research/connection-protocol/publication/test20-r3-3-strong-ref-preconnect-summary.json)
- [post-connect machine summary](../research/connection-protocol/publication/test20-r3-3-postconnect-reregister-summary.json)
