# Photos, Video, and Audio

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Visual assistant capture

In the qualified workflow, a server action instructed Hi Rokid to request a
current image from the glasses. The glasses returned a WebP frame over the
phone connection. Hi Rokid uploaded the frame to Rokid-managed object storage
and supplied the resulting object reference to the AI service.

The qualified WebP frames contained no EXIF or GPS metadata. That does not mean
the broader session lacked location or account context.

## Conversation thumbnails

Assistant thumbnails and text survived an app process restart and remained
visible while the phone was offline. They were not normal Android Gallery or
MediaStore items in the tested workflow, supporting app-private retention plus
a remote cloud object.

## Audio

The glasses operate as an open-ear audio and microphone device. Exact transport,
codec, capture, and full-duplex behavior for an independent custom app remain a
developer qualification target.

## Consumer privacy checklist

- Avoid capturing confidential screens or documents.
- Ask before recording other people.
- Review app-private history as well as the normal gallery.
- Remove media and account state before transferring ownership.
- Disable camera or microphone permissions you do not intend to use.

## Technical evidence

- [Visual workflow finding](../findings/visual-ai-workflow.md)
- [Visual test report](../tests/15-visual-ai-architecture-routing-retention.md)
