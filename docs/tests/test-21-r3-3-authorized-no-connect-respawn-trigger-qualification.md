# Test 21 r3.3 — Authorized Custom-App / No-Connect Respawn Trigger Qualification

## Question

Does a custom companion that has completed Hi Rokid authorization—but has **not** attempted CXR-L connection—cause or permit Hi Rokid to auto-respawn after the complete Hi Rokid package process group is force-stopped?

## Controlled variable

Compared with accepted r3.2 `CUSTOM_UNAUTHORIZED_ALIVE`, the only intended state change is successful authorization in the custom app.

## Prohibited operations

- no CXR-L connection attempt;
- no photo/capture action;
- no audio action;
- no Test 20 host-arm broadcast;
- no package disable/uninstall/data clear;
- no Bluetooth toggle;
- no firmware operation;
- no secondary package/process force-stop.

## Operator checkpoints

1. `HI_ROKID_CONNECTED`
2. authorize once in the custom app, return without tapping button 2, then type `AUTHORIZED_NO_CONNECT_READY`
3. after mandatory restoration, type `HI_ROKID_RECOVERY_PASS`

There is no connection-button step in this test.
