# Companion-App Requirements

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Functional requirements

| ID | Requirement |
|---|---|
| HUB-01 | Discover the exact Style device through an approved or qualified interface |
| HUB-02 | Connect and disconnect without corrupting the stock binding |
| HUB-03 | Report device identity, firmware, battery, and connection state |
| HUB-04 | Trigger and receive one local photo |
| HUB-05 | Capture microphone audio and stop deterministically |
| HUB-06 | Play bounded response audio and support interruption |
| HUB-07 | Receive physical activation events |
| HUB-08 | Communicate with a local/private backend using authenticated encryption |
| HUB-09 | Record auditable request, evidence, response, and error lineage |
| HUB-10 | Recover from app, phone, Bluetooth, device, and network interruptions |

## Safety and privacy requirements

- no captured command replay unless a separate approved protocol gate exists;
- no unexpected Rokid, OpenAI, Gemini, or other public AI fallback;
- least-privilege Android permissions;
- no raw photo or audio retention by default;
- encrypted bounded retry buffers;
- visible indication of connection, capture, and failure state;
- explicit deletion and account-unbind paths.

## Portability requirements

The application should isolate the device-specific implementation behind a
common adapter contract so a second glasses family can reuse phone-side OCR,
authentication, transport, orchestration, TTS, and audit components.
