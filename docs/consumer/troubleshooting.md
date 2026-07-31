# Troubleshooting

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Devices or firmware controls are disabled

Confirm the glasses are connected. The Devices and firmware controls were
connection-gated in the tested app.

## Pairing or reconnection problems

- Keep the glasses and phone close.
- Confirm Bluetooth and Wi-Fi are enabled.
- Relaunch Hi Rokid before forcing a glasses restart.
- Confirm the unit is not still bound to another account.
- Use the in-app pairing flow rather than generic Bluetooth pairing alone.

## Power-on or restart is unreliable

On the tested unit, nominal and forced button timings were not always reliable.
This is a lab observation, not a universal product claim.

- Avoid unnecessary restarts.
- Relaunch Hi Rokid first.
- Connect the magnetic charger and allow the unit to stabilize.
- Never force-restart during firmware installation.
- Contact Rokid support if normal power behavior remains unreliable.

## Assistant does not hear prerecorded audio

The test unit recognized wearer speech more reliably than audio played from a
nearby computer speaker. Test with live speech before concluding that the
assistant or microphones are unavailable.

## Media exists in the app but not the gallery

Assistant thumbnails can reside in app-private storage instead of normal
Android Gallery/MediaStore locations. Review Hi Rokid history as well as the
gallery.

## A Recents swipe did not stop the app

This is expected from the observed background-service behavior. Use Android
force-stop for a stronger stop boundary, then relaunch Hi Rokid when needed.

## Technical evidence

- [Background lifecycle test](../tests/16-android-background-services-package-lineage-data-sharing.md)
- [MediaStore method](../methodology/mediastore-export.md)
