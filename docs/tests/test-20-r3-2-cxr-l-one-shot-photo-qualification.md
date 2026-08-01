# Test 20 r3.2 — CXR-L One-Shot Photo Control and Bounded Image Callback Qualification

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=implementation; last_reviewed=2026-07-31 -->

## Purpose

Test 20 r3.2 is the first deliberately media-producing CXR-L stage. It issues
exactly one operator-controlled `takePhoto(1920, 1080, 80)` request after the
accepted r3.1 service-status and callback-registration gates. It accepts at most
one non-empty image callback, inspects bounded metadata in memory, never writes
or previews callback bytes, observes a duplicate-callback quiet window, and then
disconnects.

The argument labels width, height, and quality are a working hypothesis derived
from prior reverse-engineered references, not a generalized claim about every
`client-l:1.0.1` implementation. A pass qualifies only this exact triplet and
one request/callback lifecycle.

## Safety boundary

- Print the public [Test 20 r3.2 target](assets/test20-r3-2-photo-target.svg).
- Place it against a plain wall with no people, documents, displays, windows,
  identifying objects, or reflective surfaces in the camera field.
- Do not use a personal screen as the target.
- Exactly one request is permitted.
- The test app has no Internet, Camera, or Record Audio permission.
- Callback bytes are not written, previewed, uploaded, copied into publication,
  or retained by the test harness.
- Audio streaming, assistant invocation, custom commands, custom views, app
  management, pairing changes, firmware changes, and Hi Rokid force-stop are
  prohibited.

## Success criteria

1. Hi Rokid `G1.11.11.0727` and firmware `1.23.009-20260725-153201` are verified.
2. Authorization and one `CUSTOMAPP` connection succeed.
3. Image callback registration and service-status checks succeed.
4. The app reaches `ONE-SHOT PHOTO READY` before any photo request.
5. One explicit `takePhoto(1920, 1080, 80)` call returns `true`.
6. Exactly one non-empty image callback arrives before timeout.
7. No image-error or duplicate callback occurs.
8. Encoded-image format or decode-bounds metadata is recognized.
9. No payload bytes are logged, persisted, previewed, uploaded, or published.
10. Clean disconnect and normal Hi Rokid recovery pass.

## Non-claims

This stage does not establish general parameter semantics, image-quality
accuracy, camera calibration, low-light performance, transport throughput,
continuous image streaming, audio behavior, or cloud behavior.
