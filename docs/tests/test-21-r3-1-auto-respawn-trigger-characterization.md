# Test 21 r3.1 — Auto-Respawn Trigger Characterization

The first physical profile is `NO_CUSTOM_PROCESS`. It tests whether Hi Rokid returns after `am force-stop` while the custom companion is also force-stopped.

There is no authorization and no CXR-L connection attempt in this profile. During the 30-second observation window the operator performs no phone action. Hi Rokid is restored before the run can pass.

Future profiles are reserved for later qualification only after this result is reviewed: `CUSTOM_UNAUTHORIZED_ALIVE`, `CUSTOM_AUTHORIZED_NO_CONNECT`, and `CUSTOM_STOPPED_POST_AUTH`.
