# Getting Started

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Before pairing

- Charge the glasses and phone.
- Install the current Hi Rokid app from the appropriate regional app source.
- Enable Bluetooth and Wi-Fi on the phone.
- Review requested permissions before granting them.
- Create or sign in to a Rokid account when required.

## Pair through Hi Rokid

Use the app's device flow instead of treating the glasses only as a generic
Bluetooth headset. Hi Rokid manages binding and the stock device session.

A unit can remain associated with a previous account until the prior owner
unbounds it. Resolve account ownership before factory reset or repeated pairing
attempts.

## Verify the first session

1. The glasses appear connected in the Devices section.
2. Audio output and microphone pickup work.
3. Camera and media permissions match your intended use.
4. The preferred AI base model is selected.
5. The firmware version is visible while connected.
6. The local-model page reports whether the phone is eligible.

## Recommended first-day checks

- Capture one non-sensitive photo and confirm where it appears.
- Ask one non-sensitive voice question.
- Review conversation history and media retention.
- Open the firmware page without starting an update.
- Learn the normal shutdown, charging, and reconnect sequence before travel.

## Technical evidence

- [Pairing test](../tests/02-pairing-and-account-transfer.md)
- [Peripheral pairing finding](../findings/peripheral-pairing-control-path.md)
