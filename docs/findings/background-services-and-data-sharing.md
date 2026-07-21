# Android Background Services and Data Sharing

## Summary

Tests 16A–16D combined static package review, clean-install inventory,
direction-aware TLS interception, Android lifecycle snapshots, Pixel/S25
comparison, and a controlled background-mode A/B test.

Best-supported conclusions:

- “Rokid AI Service” is an embedded service in Hi Rokid, not a separately
  installed application.
- Removing Hi Rokid from Recents does not necessarily stop its process,
  foreground services, Bluetooth relationship, or AI WebSocket.
- Android force-stop is the reliable termination boundary observed in the S25
  control.
- Hi Rokid communicates with Rokid and Google/Firebase before user login.
- Pairing and AI session initialization send broad device, account, location,
  weather, model-route, and capability context.
- During stable post-swipe idle, only WebSocket ping/pong keepalives were
  observed; periodic full-context, audio, image, or prompt resends were not.
- A missing foreground notification does not prove the service is stopped.

## Package lineage

The reviewed APKS bundle contained four splits under one package:

```text
com.rokid.sprite.global.aiapp
```

A Pixel clean-install comparison changed the package count from 354 to 355.
The only added package was Hi Rokid. No delayed package appeared after first
launch, login, pairing, voice AI, visual AI, or the background-setting
transition.

Therefore:

```text
SEPARATE_ROKID_AI_SERVICE_APP=NO
SEPARATE_BAIDU_COMPANION_APP=NO
DELAYED_COMPANION_PACKAGE=NO
```

Relevant embedded components include:

- `com.rokid.sprite.aiapp.library_ai.service.AiService`
- `com.rokid.sprite.aiapp.library_connect.service.ConnectCompanionDeviceService`
- `com.rokid.sprite.aiapp.navigation.location.LocationService`

## First launch before login

After clearing Hi Rokid application data and launching without credentials,
the app contacted:

- `firebase-settings.crashlytics.com`
- `firebaseinstallations.googleapis.com`
- `firebaselogging-pa.googleapis.com`
- `rcs-internal.rokid.com`

Direction-aware analysis confirmed Firebase installation registration and
telemetry containing app/device metadata. Hi Rokid also called its Rokid token
bootstrap endpoint with an **empty** `rokidToken`. No nonempty Rokid account
token, email, password, glasses context, AI WebSocket, image, audio, precise
coordinates, or payment binding was observed in the clean unauthenticated
phase.

## Login architecture

The tested email/password login used Google Firebase Identity Toolkit and then
exchanged the resulting identity token with Rokid account services for Rokid
session tokens.

This describes the observed authentication path; no credential values are
published.

## Pairing and AI context

After the glasses were paired, the AI WebSocket opened at:

```text
wss://ai-cloud-global.rokid.com/ws/ai
```

The initial `init_scene` included category presence for:

- account/user identity;
- device and glasses identifiers/state;
- precise latitude and longitude;
- weather and local context;
- base and visual model routes;
- calendar/schedule structures;
- payment-capability configuration.

The payment object looked like a Hi Rokid capability/binding configuration.
No card, account balance, transaction, Google Wallet, or Samsung Wallet data
was observed.

## Recents swipe and screen-off behavior

In the controlled Pixel A/B test, both the banner-unsatisfied and
Unrestricted-selected arms behaved the same after removing Hi Rokid from
Recents:

- Hi Rokid process remained present;
- `AiService` remained present;
- `LocationService` remained present;
- the existing AI WebSocket remained connected;
- binary ping/pong keepalives continued approximately every ten seconds;
- no TCP reconnect or close occurred;
- no new `init_scene`, audio, image, prompt, latitude/longitude, user-ID, or
  payment-binding message appeared in the segmented idle windows.

The same behavior continued during the tested screen-off intervals.

## Background banner and notification visibility

Before the Pixel banner was satisfied, Android already reported:

```text
RUN_IN_BACKGROUND=allow
RUN_ANY_IN_BACKGROUND=allow
START_FOREGROUND=allow
```

The process and services were already active. Selecting Unrestricted battery
mode did not change the measured short-window background behavior.

The Pixel did not grant `POST_NOTIFICATIONS`, so no visible AI Service
notification appeared even though the service and WebSocket were active. The
S25 showed the notification when notification visibility was available.

Therefore:

```text
NO_VISIBLE_NOTIFICATION != NO_BACKGROUND_SERVICE
```

## Force-stop

Test 16A captured a decisive S25 boundary:

- Hi Rokid process killed;
- `AiService` and `LocationService` stopped;
- foreground notification cancelled;
- glasses RFCOMM socket disconnected;
- AI WebSocket closed;
- no automatic restart or Hi Rokid network activity during the subsequent
  screen-on and screen-off observations.

A zero-traffic PCAP was deleted by PCAPdroid in the screen-off phase, but
logcat proved the capture loop ran and reported zero hosts. That is meaningful
silence, not missing observation.

## Third-party observations

Hi Rokid-attributed traffic included Google/Firebase, Google Maps SDK,
Alipay-hosted assets, and a successful:

```text
HEAD https://www.baidu.com/
```

The Baidu request occurred during initial application activity, not during the
post-swipe idle segments. Its exact purpose remains unresolved; the evidence
does not support a claim of Baidu account use or application-payload upload.

## Limits

- The business code is packed, so static analysis cannot prove every internal
  source-to-sink path.
- The longest controlled background windows were minutes, not days.
- A future WebSocket reconnect may send a fresh `init_scene`.
- Test 16D's force-stop capture boundary was not strong enough to replace the
  authoritative Test 16A force-stop result.
- No claim is made about server-side onward sharing beyond observed phone
  endpoints and documented fields.
