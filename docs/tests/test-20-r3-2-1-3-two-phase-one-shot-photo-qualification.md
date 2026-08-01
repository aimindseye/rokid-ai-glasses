# Test 20 r3.2.1.3 — Two-Phase One-Shot Photo Qualification

## Purpose

r3.2.1.3 repaired the operator-sequencing defect by making photo arming mechanical rather than instructional. The APK kept the photo control disabled through prerequisite qualification; only a run-scoped host arm could enable one request, and the controller consumed that arm atomically before the SDK call.

## Accepted result

- firmware exact match: PASS (`1.23.009-20260725-151201`)
- app version: `1.0-test20-r3.2.1.3`
- prerequisite gate: PASS
- photo requests before host arm: `0`
- photo requests before operator tap: `0`
- final resolved photo request count: `1`
- capture dispatch: `ACCEPTED_ONCE`
- audio operation: `NONE`
- additional media action: `NO`
- Hi Rokid recovery: PASS
- image payload callback count: `0`
- image error callback count: `0`
- callback classification: `NO_IMAGE_CALLBACK`

The accepted result proves the two-phase one-shot control boundary but did not yet prove image callback delivery. That remaining boundary was isolated in r3.3.

## Sanitized evidence

- sanitized ZIP SHA-256: `3bcb4d6fe7d15af9ae6850ee5c7a64b6e0581df248e36c852e643737d9c0aa04`
- [machine-readable accepted summary](../research/connection-protocol/publication/test20-r3-2-1-3-one-shot-photo-summary.json)
