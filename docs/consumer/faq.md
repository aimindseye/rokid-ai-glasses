# Frequently Asked Questions

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=mixed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Mixed |
| Last reviewed | 2026-07-30 |


## Do these glasses have a display?

No. This wiki covers the display-free Rokid AI Glasses Style.

## Can I use them only as ordinary Bluetooth audio glasses?

Some audio behavior may work through standard phone facilities, but the stock
feature set, binding, settings, AI, media, and firmware management depend on Hi
Rokid in the tested workflow.

## Does selecting ChatGPT or Gemini prove the exact model used?

No. Different opaque routes were observed, but the exact downstream model and
provider contract were not exposed.

## Is the assistant fully local when a local model is installed?

Not proven. A local component and phone compatibility gate were observed, while
the qualified assistant workflow remained cloud-mediated.

## Are visual-assistant images uploaded?

Yes in the qualified stock workflow. Hi Rokid uploaded the glasses frame to
Rokid-managed object storage before the AI request referenced it.

## Does swiping Hi Rokid away stop it?

Not necessarily. Services and the AI connection continued after a Recents swipe
in the tested paired state. Android force-stop was the stronger boundary.

## Can I install apps or use ADB?

USB ADB was available on the tested unit while Developer Mode was enabled. This
is a developer capability, not proof that arbitrary apps, privileges, or custom
firmware are safe or compatible.

## Is there already a replacement Hi Rokid app?

No complete replacement app has been delivered. The developer roadmap begins
with Style qualification of supported SDK/CXR interfaces.

## Technical evidence

- [Developer current status](../developer/current-status.md)
- [Research library](../research/README.md)
