# Bluetooth and Media Interfaces

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Proven foundation

The accepted independent client opened and closed the attributed RFCOMM service
with SCN `3`, DLCI `6`, MTU `990`, and zero application bytes in both
directions. This proves transport reachability, not the complete application
protocol.

## Stock Developer Mode message family

Four qualified stock actions established a bounded outbound grammar with
self-inclusive outer and nested lengths, stable field order, a one-byte
monotonic sequence candidate, an action discriminator, and structured `on` or
`off` state. Replies, authorization, integrity, session binding, and safe custom
transmission remain unresolved.

## Media qualification still required

- camera trigger and file transfer interface;
- still-image format, resolution, orientation, and latency;
- microphone transport, codec, rate, channels, and stop semantics;
- speaker transport, volume, interruption, and latency;
- full-duplex behavior and echo control;
- physical input and lifecycle event channels.

## Prohibited shortcut

Do not replay captured application payloads or implement a sender solely from
the observed four-message family. Use an approved SDK or first recover positive
reply, authorization/integrity, sequence, session, failure, and rollback
semantics.

## Evidence

- [Connection-protocol index](../../research/connection-protocol/README.md)
- [Stock ADB-toggle publication](../../research/connection-protocol/stock-adb-toggle/README.md)
- [Independent Android client](../../../android-client/README.md)
