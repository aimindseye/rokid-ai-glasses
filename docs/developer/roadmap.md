# Development Roadmap

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Track A — Replacement Android companion app

1. Qualify CXR-M or another supported mobile interface on the exact non-display
   unit.
2. Determine Hi Rokid session ownership and coexistence.
3. Trigger local photo capture and receive the file without Rokid cloud use.
4. Qualify microphone input, speaker playback, and full-duplex behavior.
5. Map physical controls and AI activation events.
6. Complete one synthetic local AI round trip.
7. Prove offline/no-cloud operation and lifecycle recovery.

## Track B — On-glasses software and firmware

1. Install and run a minimal signed APK over qualified USB ADB.
2. Map ordinary, signature, privileged, and SELinux-protected capabilities.
3. Add only the smallest glasses-side bridge required by Track A.
4. Build an immutable partition and recovery baseline.
5. Attempt temporary or reversible boot research only after recovery is proven.
6. Preserve proprietary vendor camera, audio, Bluetooth, TEE, and calibration
   components unless clean replacements exist.

## Track C — Common SmartGlasses platform

1. Define a device-adapter contract for camera, microphone, speakers, controls,
   status, and lifecycle.
2. Implement the Android phone as the hub for permissions, OCR, authentication,
   buffering, and transport.
3. Implement the local or private backend as the brain for orchestration, RAG,
   structured APIs, and audit.
4. Prove a synthetic vertical slice before connecting sensitive production
   systems.
5. Add additional glasses only through qualified adapters.

## Decision rule

Prefer stock firmware plus a custom phone app. Add a small on-glasses APK only
when required. Modify firmware only when the application and permission
boundaries block a necessary capability and a complete recovery route exists.
