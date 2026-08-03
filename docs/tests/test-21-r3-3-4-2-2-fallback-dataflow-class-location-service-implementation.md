# Test 21 r3.3.4.2.2 — Fallback Intent Register/Data-Flow Closure, SDK Connect Decision-Branch Recovery, CXRLinkService Class-Location Census, and IMediaStreamService Service-Implementation Recovery

## Purpose

This test is offline-only. It follows accepted r3.3.4.2.1 and addresses the two remaining static-analysis gaps before replacement-service design:

1. trace the actual registers/objects reaching `Context.bindService()` inside `CxrLPhotoController.bindServiceFallback()` and recover the exact Intent action/package, binding flags, and the names of extras without exposing authorization values; and
2. census every `classes*.dex` in every preserved Hi Rokid APK for actual class definitions versus mere references for `CXRLinkService`, `IMediaStreamService`, `$Stub`, `$Stub$Proxy`, and `$Stub` subclasses, then attempt `CXRLinkService.onBind()` → Binder implementation closure.

## Hard proof boundaries

A literal existing somewhere in the method is not sufficient for an exact Intent result. `FALLBACK_INTENT_DATAFLOW_DISPOSITION=EXACT_REGISTER_DATAFLOW_TO_BIND_SERVICE` requires the reconstructed Intent object reaching `bindService()` to carry the known action and global package, with flags `1`.

A descriptor appearing in a string/type table is not a class definition. Class location is reported separately as `CLASS_DEF_FOUND`, `REFERENCE_ONLY_NO_CLASS_DEF`, or `NOT_PRESENT_IN_PRESERVED_APK_SET`.

The authorization token value is never copied into sanitized evidence. Only the presence of the `auth_token` extra key and the source kind of its value are retained.

## Scope

- existing r3.3.4.1 private APK set only;
- no ADB or device operation;
- no network capture;
- no Hi Rokid force-stop;
- no CXR-L connection attempt;
- no photo/audio operation.
