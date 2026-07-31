# Replacement Companion Application

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Goal

Build an Android hub that can connect to the stock non-display glasses, receive
user input and media, communicate with a local/private backend, and return audio
through supported Hi Rokid/CXR-L coexistence first, while independent replacement remains a later goal.

## Initial scope

- discover and connect to the glasses;
- report identity, firmware, battery, and connection state;
- trigger one photo and receive it locally;
- capture microphone audio;
- play response audio;
- receive physical-control events;
- recover after phone, app, Bluetooth, and glasses lifecycle changes;
- fail closed instead of silently falling back to public cloud services.

## Deliberate non-goals for the first build

- custom firmware;
- independent stock-command replay;
- replacing every Hi Rokid consumer feature;
- display rendering;
- always-listening wake words;
- production use with sensitive data before privacy and audit gates pass.

## Documents

- [Requirements](requirements.md)
- [Test plan](test-plan.md)
- [Test 19 r2: Hi Rokid CXR-L firmware comparison](test-19-r2-qualification.md)
- [Withdrawn Test 19 r1 CXR-M experiment](test-19-r1-qualification.md)
- [Lifecycle and recovery](lifecycle.md)
- [SDK/CXR qualification](../sdk-and-cxr/README.md)
- [Bluetooth and media](../bluetooth-and-media/README.md)
