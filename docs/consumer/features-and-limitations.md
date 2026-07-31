# Features and Limitations

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=mixed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Mixed |
| Last reviewed | 2026-07-30 |


## Display-free design

The glasses support audio-first and camera-assisted workflows. They do not
provide in-lens text, HUD subtitles, or a visual navigation overlay. Projects
built around display rendering do not automatically transfer to Style.

## AI assistant

Hi Rokid offered ChatGPT and Gemini selections during testing and propagated
different opaque route identifiers. The exact downstream model, provider
contract, and system prompt were not exposed to the project.

## Visual assistant

The tested visual workflow used the glasses camera, returned a WebP frame to the
phone, uploaded it to Rokid-managed object storage, and referenced the uploaded
object during the AI request. Conversation text and thumbnails survived an app
process restart and were available while the phone was offline.

## Translation

Behavior can vary by mode, language, app version, region, and phone. One tested
configuration displayed results on the phone and marked glasses audio
unsupported. Do not generalize that result to every translation mode.

## Local models

Hi Rokid applies a phone compatibility gate. A Qwen3-family `Wend_Audio`
component was observed, but the tested assistant response path remained
cloud-mediated. A phone passing normal pairing does not necessarily pass the
local-model gate.

## Development features

The tested unit exposed RSA-protected USB ADB when Developer Mode was enabled.
It remained a production build and was not proven safe for flashing. Consumer
users should leave development features disabled unless actively needed.

## Technical evidence

- [AI routing finding](../findings/ai-assistant-routing.md)
- [Translation architecture](../findings/translation-architecture.md)
- [USB ADB finding](../findings/glasses-android-os-and-adb.md)
