# Test 20 Final — CXR-L One-Shot Photo and Image-Callback Closure

## Accepted environment

- Rokid AI Glasses Style firmware: `1.23.009-20260725-151201`
- Hi Rokid: `G1.11.11.0727`
- SDK: `com.rokid.cxr:client-l:1.0.1`
- resolved AAR SHA-256: `c23d34b3adc60d3fa16001645ce6172eaf4554173e7ef9c078595e672d50824e`

## Accepted evidence lineage

The publication is derived only from reviewed sanitized summaries. Private evidence ZIPs, screenshots, raw device identifiers, authorization tokens, operator-arm token values, and image payloads remain local and are not published.

| Run | Sanitized ZIP SHA-256 | Accepted result |
| --- | --- | --- |
| r3.2.1.3 two-phase one-shot gate | `3bcb4d6fe7d15af9ae6850ee5c7a64b6e0581df248e36c852e643737d9c0aa04` | exactly one bounded request; no image callback |
| r3.3 `STRONG_REF_PRECONNECT` | `96716c665f268f543686b7fcc9d2b8f87526c835d8a4994d21c908c1371b0ce5` | request accepted; service stable; no image callback |
| r3.3 `POSTCONNECT_REREGISTER` | `dd8b8580e484968bdb75b20c6d00188d2b564efa1697b52e17f461bf3502b35c` | request accepted; one image payload callback delivered |

## Closure

r3.2.1.3 proved the script/APK synchronization and two-phase host-tokenized one-shot gate. The machine evidence recorded zero photo requests before host arming, zero requests before the operator tap, one resolved request after arming, no audio operation, no additional media action, and successful Hi Rokid recovery. The image callback remained unresolved in that run.

r3.3 isolated the callback path. Retaining a strong `IImageStreamCbk` reference and registering it before connection still produced `REQUEST_ACCEPTED_NO_CALLBACK_SERVICE_STABLE`. Re-registering the same retained callback after CXR-L connection/service establishment, while keeping `takePhoto(1920,1080,80)`, produced `IMAGE_CALLBACK_DELIVERED` with one payload callback and zero image-error callbacks.

The bounded conclusion is therefore that **post-connect callback registration timing/session establishment is strongly implicated**. The successful behavioral rule is to retain the callback strongly, register it before connect, re-register that same object after successful service-status qualification, and only then permit photo arming.

This does not prove that CXR-L internally clears or replaces the callback, and it does not generalize the behavior beyond the tested firmware/Hi Rokid/`client-l:1.0.1` environment.

## Canonical implementation rule

The canonical Test 20 photo controller now:

1. retains one strong `IImageStreamCbk` instance for the run;
2. registers it before CXR-L connection;
3. waits for CXR-L connected, glasses Bluetooth connected, and successful service-status queries;
4. re-registers the same retained callback object after those status gates;
5. fails closed if the post-connect re-registration fails or the callback identity changes;
6. marks the photo path ready only after the re-registration succeeds;
7. preserves the r3.2.1.3 two-phase host-tokenized arm and atomic one-shot consumption;
8. issues at most one `takePhoto(1920,1080,80)` request per run;
9. performs no audio-stream, preview, payload-persistence, upload, or cloud operation.

## Explicitly unresolved

- the internal SDK/service mechanism responsible for the pre-connect-only callback non-delivery;
- the semantic meaning of the third `takePhoto` argument; `ARG3_ZERO_DIAGNOSTIC` was not run because it was no longer justified;
- generalization to other firmware, Hi Rokid, or SDK versions;
- direct camera capture without Hi Rokid authorization/media-service participation;
- microphone and speaker qualification.

## Final disposition

`TEST20_FINAL_STATUS=ACCEPTED_CLOSED_IMPLEMENTATION_RULE_PUBLISHED`
