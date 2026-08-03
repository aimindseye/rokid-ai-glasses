# Test 21 r3.3.2 — Authorized Foreground→Background Lifecycle Transition and Respawn Trigger Characterization

## Question
Does one controlled foreground→background lifecycle transition, after successful authorization but before any CXR-L connection attempt, create or expose a custom→Hi Rokid binding or make the Hi Rokid package respawn after a complete package force-stop?

## Accepted prerequisite
This overlay requires the exact repaired Test 21 r3.3.1 implementation. It refuses installation if any prerequisite hash differs.

## Enabled physical profile
`AUTHORIZED_FOREGROUND_TO_BACKGROUND_HOME_15S`

1. Hi Rokid is initially open and the glasses are connected normally.
2. The custom companion is freshly launched and authorized once.
3. The custom app is machine-proven alive and foreground.
4. The host issues exactly one `KEYCODE_HOME` through ADB. The operator does not press Home manually.
5. The custom process must remain alive and must be machine-proven background immediately and after 15 seconds.
6. Binder/service/process state is captured before and after the lifecycle transition.
7. Hi Rokid is force-stopped exactly once and all same-package processes must be absent.
8. A 30-second hands-off respawn window follows.
9. The custom app is stopped and Hi Rokid is restored.

## Safety boundaries
- Authorization: one controlled attempt.
- CXR-L connection attempt: none.
- Host photo arm: none.
- Photo/audio: none.
- Package disable/uninstall/data-clear: none.
- Bluetooth toggle: none.
- Secondary package force-stop: none.
- Hi Rokid force-stop: exactly one controlled attempt after lifecycle gates pass.

## Interpretation
A caller-bound relationship that is absent in `foreground-before` but appears in `background-00` or `background-15` is evidence that the lifecycle transition created/exposed a binding candidate. A respawn after the same transition, when earlier r3.3.1 foreground-delay remained stopped, strengthens the lifecycle-trigger hypothesis. If neither occurs, the next useful step is a differential replication of the original r3 operator/session sequence rather than layering more variables.
