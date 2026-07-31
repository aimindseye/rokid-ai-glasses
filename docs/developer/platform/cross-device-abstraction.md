# Cross-Device Abstraction

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Adapter contract

```text
DeviceInfo get_info()
Capabilities get_capabilities()
connect()
disconnect()
capture_photo(options)
start_microphone(options)
stop_microphone()
play_audio(stream)
stop_audio()
subscribe_controls()
subscribe_lifecycle()
```

## Capability negotiation

Do not infer features from a product name. Each adapter reports support for:

- still photo;
- video;
- microphone stream;
- speaker playback;
- full duplex;
- buttons or gestures;
- display text, image, or navigation;
- battery and thermal state;
- firmware and update state;
- offline operation.

## Error model

Use common errors such as `permission_required`, `not_supported`,
`device_busy`, `disconnected`, `transfer_failed`, `authentication_required`,
and `backend_unavailable`. Preserve device-specific diagnostics privately while
returning bounded public messages.

## Initial adapters

The first adapter is the non-display Rokid Style. Other glasses should be added
only after their own transport, permissions, privacy, and lifecycle tests pass.
