# Visual AI Workflow

## Summary

A visual question is not handled by continuously streaming camera video.
Instead, Rokid's server decides that a photo is required and instructs Hi Rokid
to obtain a fresh still image from the glasses.

```text
Visual speech
  → server ASR
  → take_photo tool
  → glasses WebP over Bluetooth
  → Rokid OSS upload
  → processing_image object URL
  → visual route
  → text and synthesized speech
```

## Capture trigger

The visual workflow begins after server-side speech recognition returns a
`take_photo` tool action. Merely opening or remaining in Assistant did not
capture an image.

Observed command:

```text
Ai_TakePhoto {"width":1440,"height":1080,"quality":70}
```

## Image movement

| Stage | Observed representation |
|---|---|
| Glasses → phone | WebP over Bluetooth |
| Phone → object storage | Multipart HTTPS upload |
| Phone → AI WebSocket | Regional OSS object URL |
| Assistant history | App-private thumbnail/cache |

Images were `1080 × 1440`, contained no EXIF/GPS metadata, and were not
published through normal Android MediaStore.

## Visual routing

| Selection | `vl_model_no` |
|---|---|
| ChatGPT | `5d9h11m6qk10s8p12` |
| Gemini | `gEmEcBf6rTsSwdRc` |

A live ChatGPT-to-Gemini transition changed `vl_model_no` within the same
conversation. The visual `base_model_no` remained fixed.

## Follow-ups

The tested policy depends on the question:

- vague reference to a prior image → clarification, no new photo;
- specific question about a visible detail → fresh current-scene capture.

Both ChatGPT and Gemini grounded follow-ups generated new photos and new
conversation thumbnails. Reuse of the prior image for a grounded follow-up was
not observed.

## Retention

Question text, answer text, and thumbnails survived a Hi Rokid process restart
and remained visible while the phone was offline.

This confirms a persistent app-private cache. The original full-size image is
also uploaded as a remote object, so the architecture is hybrid.

## TTS

Rokid's AI WebSocket supplied synthesized audio, which Hi Rokid forwarded to
the glasses over Bluetooth.

Google phone TTS initialized but was not observed generating the answer.
Microsoft/Azure TTS was not confirmed.

## Privacy

Public documentation must not contain:

- raw image frames or conversation screenshots;
- complete object URLs;
- OSS authorization values;
- account, session, device, or location context;
- PCAPs, TLS keys, logcat, HCI logs, or bugreports.

See [Test 15](../tests/15-visual-ai-architecture-routing-retention.md).
