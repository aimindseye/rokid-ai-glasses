# Test 21 r3 — Bound-Service Respawn Dependency Characterization

## Purpose

Test 21 r2 proved that the canonical custom companion can begin a CXR-L session while
`com.rokid.sprite.global.aiapp` is stopped, but the Hi Rokid process becomes visible
again during or after session establishment.

Test 21 r3 narrows that dependency boundary. It observes the first Hi Rokid process
reappearance and correlates it with:

- custom-app `connection_attempt_started`;
- `callback_cxrl_connected`;
- `callback_glass_bt_connected`;
- `service_status_result`;
- the prerequisite-ready/photo-ready machine state;
- Android ActivityManager event-buffer evidence;
- runtime `dumpsys activity services` snapshots;
- service/component identities visible at the first process respawn.

The test characterizes ordering and visible service/binding evidence. It does **not**
claim Binder causality merely because two events occur near each other.

## Accepted prerequisite

Test 21 r2 disposition:

`CUSTOM_SESSION_CONNECTED_HI_ROKID_RESPAWNED`

The r3 source contract requires the exact accepted r2 repair-1 tooling by SHA-256.

## Mutation boundary

Permitted runtime mutation:

- exactly one `adb shell am force-stop com.rokid.sprite.global.aiapp`;
- bounded custom-companion force-stop during setup/cleanup;
- explicit Hi Rokid launcher restoration.

Not permitted:

- package disable;
- uninstall;
- package-data clear;
- firmware change;
- Bluetooth toggle;
- logcat clear;
- photo request;
- audio operation;
- Test 20 host photo-arm command.

The authorization token stays in the already-running custom app's memory and is
never exported or persisted by Test 21.

## Observation design

The host starts passive `logcat` streams without clearing existing device logs.
After Hi Rokid process absence is proven and the custom companion remains alive,
the runner starts a short high-frequency observer.

The observer samples:

- whether the Hi Rokid process is visible;
- whether the custom companion remains visible;
- first observation of selected custom-app connection events;
- `dumpsys activity services` snapshots.

At the first observed Hi Rokid process transition from absent to present, it captures
additional private runtime snapshots.

The timestamps are **host observation times**, not proof of device-side causal
ordering. The sanitized summary explicitly preserves this limitation.

## Principal dispositions

- `AUTO_RESPAWN_BEFORE_CONNECTION_ATTEMPT`
- `RESPAWN_AFTER_CONNECTION_ATTEMPT_BEFORE_CXRL_CONNECTED`
- `RESPAWN_AFTER_CXRL_BEFORE_SERVICE_STATUS`
- `RESPAWN_AFTER_SERVICE_STATUS_BEFORE_PREREQUISITE_READY`
- `RESPAWN_AFTER_PREREQUISITE_READY`
- `NO_RESPAWN_DURING_OBSERVATION`
- `INSUFFICIENT_TIMELINE_EVIDENCE`

## Service evidence

The analyzer separately reports:

- `BOUND_SERVICE_CALLER_EVIDENCE`
- `BOUND_SERVICE_EVIDENCE`
- `PROCESS_START_EVENT_EVIDENCE`
- `HI_ROKID_SERVICE_COMPONENTS_AT_RESPAWN`

`BOUND_SERVICE_CALLER_EVIDENCE=YES` is deliberately strict: the same captured
ActivityManager/service line must identify the custom companion, Hi Rokid, and a
binding concept. Merely observing a Hi Rokid service after respawn is not treated as
proof that the custom app directly bound it.

## Privacy

Keep the complete evidence root private. Raw evidence can contain package paths,
process state, ActivityManager output, Bluetooth diagnostics, and other device
metadata.

Only upload the generated sanitized summary ZIP and its `.sha256` sidecar.
