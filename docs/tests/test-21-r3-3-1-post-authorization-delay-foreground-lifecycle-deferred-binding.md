# Test 21 r3.3.1 — Post-Authorization Delay, Foreground/Lifecycle, and Deferred-Binding Respawn Characterization

## Question
Does an authorization-created CXR/Hi Rokid binding appear only after a bounded foreground settling interval, even when no explicit CXR-L connection attempt occurs?

## Enabled physical profile
`AUTHORIZED_FOREGROUND_DELAY_30S` only. The custom app must remain visibly foreground for the full 30-second post-authorization settling interval. A future foreground/background transition profile is intentionally not enabled until this result is reviewed.

## Controlled sequence
1. Confirm normal Hi Rokid/glasses baseline.
2. Fresh-launch custom companion and authorize once through Hi Rokid.
3. Return to the custom companion and keep it foreground.
4. Prove authorization token presence without exporting the token value and prove no CXR-L/session/media event occurred.
5. Capture service/process/activity state at settle 0s, 15s and 30s.
6. Force-stop Hi Rokid exactly once and prove all same-package processes are down.
7. Observe 30 seconds for respawn and capture process-start/binder/service evidence.
8. Stop the custom companion, restore Hi Rokid, and require operator recovery confirmation.

## Prohibited
No button-2 connection action; no capture; no audio; no package disable/uninstall/data clear; no Bluetooth toggle; no secondary-package force-stop; no token export.

## Interpretation
A caller binding that first appears at settle-15 or settle-30 is evidence for deferred post-authorization initialization. No pre-force binding plus no post-force respawn moves the next controlled variable to a foreground/background lifecycle transition profile.
