# Product Overview

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=mixed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Mixed |
| Last reviewed | 2026-07-30 |


## What it is

Rokid AI Glasses Style is a display-free, audio-first pair of smart glasses with
a camera, microphones, open-ear speakers, wireless connectivity, and a phone
companion application.

## Typical consumer uses

- voice assistant interaction;
- first-person photo and video capture;
- visual questions about the current scene;
- translation and transcription workflows;
- calls and open-ear audio;
- device settings, media review, and firmware updates through Hi Rokid.

Feature availability can vary by app version, firmware, region, account, phone,
and selected mode.

## Published hardware snapshot retained by this project

| Component | Repository snapshot |
|---|---|
| Main compute | Qualcomm AR1 Gen 1 |
| Low-power compute | NXP RT600 family |
| Memory | 2 GB RAM |
| Storage | 32 GB |
| Camera | 12 MP Sony IMX681 |
| Wireless | Wi-Fi 6 and Bluetooth 5.3 |
| Input | Four directional microphones |
| Output | Dual open-ear speakers |
| Battery | 210 mAh |
| Display | None |

Treat this as a documented snapshot, not a guarantee for every regional or
hardware revision.

## Role of Hi Rokid

In the tested stock workflow, Hi Rokid handled pairing and binding, device
settings, model selection, visual uploads, AI sessions, retained conversation
state, and firmware checks.

## Technical evidence

- [Device profile](../reference/device-profile.md)
- [System architecture](../reference/device-profile.md#observed-system-role)
- [Detailed observed architecture](../architecture/non-display-system-architecture.md)
