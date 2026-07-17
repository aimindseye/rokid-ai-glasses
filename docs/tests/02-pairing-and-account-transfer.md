# Test 02 — Pairing and Account Transfer

## Exact scenario

The glasses were initially associated with an account controlled by the
owner. The owner explicitly unbound the glasses from that account before
binding them to a different test account.

This test did **not** evaluate bypassing an activation lock or reusing stolen
bound hardware.

## Result

Completed on 2026-07-16 with label:

    02b-owner-unbound-account-change-and-rebind

The application warned that clearing glasses data and rebinding would remove
local photos, videos, recordings, and third-party applications. The owner
accepted that operation and the glasses successfully bound to the new test
account.

Observed transport and service activity included:

- BLE and GATT
- Classic Bluetooth and RFCOMM
- Rokid XR, AI, device-account, RCS, and OTA services

Logcat recorded a successful Rokid account-change result, followed closely by
`device-account-prod.rokid.com` activity.

## Interpretation

The evidence demonstrates an owner-authorized account transfer after explicit
unbind. It does not establish whether a previously bound device can be
recovered without the prior account owner's authorization.
