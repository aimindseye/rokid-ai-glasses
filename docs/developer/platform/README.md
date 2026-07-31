# Common SmartGlasses Platform

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Goal

Create a reusable platform in which each glasses family supplies a thin device
adapter while the phone and backend reuse capture, OCR, authentication,
transport, orchestration, RAG, structured APIs, TTS, and audit services.

## Core documents

- [Device–hub–brain architecture](device-hub-brain-architecture.md)
- [Cross-device abstraction](cross-device-abstraction.md)
- [Security and privacy](security-and-privacy.md)

## First vertical slice

Use one synthetic screen image, one synthetic entity identifier, one spoken
command, one deterministic local response, one TTS playback, and one audit
record.

```text
button
→ glasses photo and voice
→ phone OCR and authenticated request
→ local/private backend
→ grounded response
→ phone TTS
→ glasses speaker
→ immutable audit record
```

Do not connect real customer or regulated data until the synthetic slice,
privacy boundary, RBAC, evidence grounding, and audit lineage pass.
