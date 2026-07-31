# Firmware Updates

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Connection requirement

The firmware page and update controls required connected glasses in the tested
app. A cold app launch, entering the firmware page, and pressing the manual
check each produced fresh live OTA requests.

## Before an update

- Charge the glasses and phone.
- Use stable connectivity.
- Confirm the glasses remain connected.
- Avoid forced restart, cable removal, or account changes during installation.
- Record the displayed current version without publishing device identifiers.

## “Latest version” interpretation

The tested service could return multiple version-related fields while the app
still displayed “latest.” The result appears to use more than a simple numeric
comparison of one visible string.

## Development warning

The repository contains read-only OTA and boot-chain research, but no custom
image has been booted or flashed. A reported unlocked/orange verified-boot state
does not prove that modification or recovery is safe.

## Technical evidence

- [Consumer firmware finding](../findings/ota-and-firmware.md)
- [Technical OTA appendix](../findings/ota-and-firmware-technical-appendix.md)
- [Firmware test](../tests/14b-firmware-update-discovery.md)
