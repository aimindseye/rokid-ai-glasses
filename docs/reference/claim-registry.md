# Claim Registry

<!-- wiki-status: audience=reference; applies_to=rokid-ai-glasses-style-non-display; evidence=mixed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Reference |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Mixed |
| Last reviewed | 2026-07-30 |


This registry provides concise reusable claims and their evidence boundaries.
It does not replace the underlying test or research publication.

| Claim | Level | Boundary | Evidence |
|---|---|---|---|
| Style is display-free | Official/modeled | Exact product scope | [Identify your model](../consumer/identify-your-model.md) |
| Tested unit runs Android 12/API 32 | Observed | Qualified US unit | [USB ADB finding](../findings/glasses-android-os-and-adb.md) |
| Phone was the stock AI network gateway | Observed | Qualified idle, voice, and visual states | [Architecture](../architecture/non-display-system-architecture.md) |
| Visual frame was uploaded before AI use | Observed | Qualified visual workflow | [Visual finding](../findings/visual-ai-workflow.md) |
| Recents swipe did not stop Hi Rokid runtime | Observed | Tested paired state | [Background finding](../findings/background-services-and-data-sharing.md) |
| Independent RFCOMM open/close works | Observed | Accepted connection-only workflow | [Final closure](../research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md) |
| Full replacement companion exists | Unverified/false | Not delivered | [Developer status](../developer/current-status.md) |
| Custom firmware is safe to flash | Unverified | Recovery not proven | [Firmware track](../developer/firmware/README.md) |
