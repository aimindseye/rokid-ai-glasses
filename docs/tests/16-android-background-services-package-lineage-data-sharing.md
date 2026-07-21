# Test 16 — Android Background Services, Package Lineage, and Data Sharing

## Status

**PASS in documented scope.**

Test 16 is a consolidated qualification set:

| Subtest | Device/state | Primary question | Result |
|---|---|---|---|
| 16A | Existing paired S25, post-AI | What survives Recents dismissal and what does force-stop terminate? | PASS |
| 16B | Clean Pixel install | Does installation add another app, and what communicates before/after login? | PASS |
| 16B-r2 | Pixel app-data clear | Was the apparent pre-login Rokid token real? | PASS — empty token bootstrap |
| 16C-r2 | Paired Pixel | What is sent during pairing, AI initialization, voice/visual use, dismissal, and relaunch? | PASS |
| 16D | Paired Pixel A/B | Does the in-app background banner change actual runtime behavior? | PASS — no measured short-window effect |

## Test subject

```text
Application: Hi Rokid
Package:     com.rokid.sprite.global.aiapp
Version:     G1.10.11.0713
Version code: 10100011
```

Reviewed APKS SHA-256:

```text
df99ba51906e1c7866135d7cd1400fca62eae4205eed78c1c8730da3d33cdc3a
```

Raw private evidence, TLS secrets, account values, device identifiers,
coordinates, screenshots, and APKs are not stored in this repository.

## 16A — S25 lifecycle baseline

### Recents dismissal

After the visible Hi Rokid task was removed, periodic Android snapshots still
showed the same Hi Rokid process, `AiService`, and `LocationService`. The
existing authenticated AI WebSocket remained open and exchanged ping/pong
frames.

No new post-dismissal audio, image, or AI prompt was observed. Sensitive
`init_scene` context had been sent when the WebSocket initialized before the
swipe.

### Force-stop

The S25 log boundary showed package force-stop killing the process, stopping
`AiService` and `LocationService`, cancelling the foreground notification,
disconnecting RFCOMM, and closing the AI socket. The package did not restart
during the screen-on or screen-off observation.

The screen-off capture produced no traffic. PCAPdroid deleted its empty PCAP,
but its own log confirmed an active capture loop and zero hosts.

### Relaunch

Launching Hi Rokid restarted the services, re-established RFCOMM, restored
live battery data, and reopened the cloud session. A transient disconnected
popup in this baseline was consistent with an Activity/service initialization
race.

## 16B — clean Pixel installation and first run

### Package comparison

```text
Before installation: 354 packages
After installation:  355 packages
Only added package:   com.rokid.sprite.global.aiapp
```

The installed base and split APK hashes matched the reviewed APKS contents.
No delayed package appeared after first launch or login.

### First launch before login

Hi Rokid contacted Rokid and Google/Firebase before user login. Decrypted
operations included:

```text
GET  Firebase Crashlytics settings
POST Firebase installation registration
POST Firebase logging batch
POST Rokid getLoginTokenByRokidToken
```

A subsequent data-clear repair proved the phone-to-server `rokidToken` value
was empty. Firebase returned a nonempty installation token, which is an app
installation credential rather than a Rokid user session.

Confirmed pre-login metadata categories included application version/build,
phone manufacturer/model, Android build, locale/country, network type,
timezone, and Firebase installation identity.

Not observed before login:

- email or password;
- nonempty Rokid account token;
- glasses identifiers or battery;
- AI WebSocket;
- voice or visual upload;
- precise latitude/longitude;
- payment binding;
- installed-app-list payload;
- Baidu request.

### Login

The tested email/password flow used Google Firebase Identity Toolkit, followed
by Rokid token exchange and Rokid account APIs. Values remain private.

## 16C-r2 — pairing and paired data sharing

The Pixel used the same Rokid account and the glasses were transferred only
after the logged-in/unpaired capture completed. No glasses restart,
power-cycle, or factory reset was requested.

Pairing introduced device login/binding operations and opened the Rokid AI
WebSocket. The direction-aware sanitizer confirmed nonempty user ID and precise
latitude/longitude fields in the phone-to-server `init_scene`, together with
device state, weather, calendar structures, payment capability configuration,
and model routes.

Voice and visual controls reproduced the previously documented Rokid-mediated
assistant flows. No additional Android package appeared after pairing, voice
AI, visual AI, Recents dismissal, force-stop controls, or relaunch.

The Pixel had no notification permission for Hi Rokid, explaining why the
operator saw no AI Service notification despite active runtime state.

## 16D — Pixel background-mode A/B

### A/B design

Arm A captured the paired runtime while the in-app background banner remained
unsatisfied. The operator then used **Go to enable**, opened Android App battery
usage, selected Unrestricted, and repeated the same actions in Arm B.

Each arm used one continuous, direction-aware TLS capture segmented into:

1. paired idle;
2. Recents dismissed, screen on;
3. Recents dismissed, screen off.

### Android controls

Before the banner was satisfied:

```text
RUN_IN_BACKGROUND=allow
RUN_ANY_IN_BACKGROUND=allow
START_FOREGROUND=allow
standby bucket=5 (exempted)
device-idle allowlisted=yes
companion association=yes
```

After selecting Unrestricted:

```text
RUN_IN_BACKGROUND=allow
RUN_ANY_IN_BACKGROUND=allow
START_FOREGROUND=allow
standby bucket=10 (active)
device-idle allowlisted=no
```

The app-ops remained allowed. The process and services were already active
before the transition.

### Segmented result

| Segment | Arm A | Arm B |
|---|---|---|
| Process after Recents swipe | Present | Present |
| `AiService` | Present | Present |
| `LocationService` | Present | Present |
| Screen-off survival | Yes | Yes |
| WebSocket keepalive | About one ping/pong per 10 seconds | About one ping/pong per 10 seconds |
| TCP reconnect/close | None | None |
| Fresh sensitive context resend | Not observed | Not observed |

The A/B behavior was effectively identical during the tested windows.

### Notification visibility

`POST_NOTIFICATIONS` was not granted on the Pixel. The service and WebSocket
remained active without a visible AI Service notification.

### Background network content

The initial paired connection sent `init_scene`. The post-swipe screen-on and
screen-off segments contained only WebSocket ping/pong events. No fresh audio,
image, prompt, user ID, latitude/longitude, payment binding, or `init_scene`
was observed in those segments.

## Third-party endpoints

Observed Hi Rokid-attributed infrastructure included Rokid services,
Google/Firebase, Google Maps SDK, Alipay-hosted assets, and a successful
`HEAD /` request to `www.baidu.com` during initial app activity.

The Baidu purpose remains unresolved. It was not observed as a separate
installed package and did not appear in the post-swipe idle segments.

## Final assertions

```text
ROKID_AI_SERVICE_OWNER=com.rokid.sprite.global.aiapp
SEPARATE_AI_SERVICE_APP=NO
DELAYED_COMPANION_PACKAGE=NO

PRELOGIN_EXTERNAL_COMMUNICATION=YES
PRELOGIN_FIREBASE_INSTALLATION_AND_LOGGING=YES
PRELOGIN_NONEMPTY_ROKID_USER_TOKEN=NO

PAIRING_AI_INIT_SCENE_SENSITIVE_CONTEXT=YES
PAYMENT_CREDENTIALS_OBSERVED=NO
GOOGLE_OR_SAMSUNG_WALLET_DATA_OBSERVED=NO

RECENTS_SWIPE_TERMINATES_PROCESS=NO
SCREEN_OFF_TERMINATES_SERVICE=NO
BACKGROUND_WEBSOCKET_KEEPALIVE=YES
PERIODIC_FULL_CONTEXT_RESEND=NOT_OBSERVED

VISIBLE_NOTIFICATION_REQUIRED_FOR_SERVICE=NO
BACKGROUND_BANNER_REFLECTS_ACTUAL_RUNTIME=NO

FORCE_STOP_TERMINATES_RUNTIME=YES (Test 16A control)
```

## Limitations

- Test 16A raw evidence remains private; only its hash and reviewed summary are
  public.
- Background windows were several minutes, not long-term soak tests.
- No reconnect occurred inside the segmented post-swipe windows; reconnect may
  trigger a new `init_scene`.
- Test 16D force-stop segmentation was weaker than Test 16A and is not used as
  the authoritative force-stop conclusion.
- Static source-to-sink analysis remains limited by application packing.
