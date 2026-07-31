# Bluetooth Profile

<!-- wiki-status: audience=reference; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Reference |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Qualified independent connection

| Field | Result |
|---|---|
| RFCOMM server channel | 3 |
| DLCI | 6 |
| MTU | 990 |
| Open lifecycle | SABM / UA observed |
| Close lifecycle | DISC / UA observed |
| Application bytes in accepted connection-only attempt | TX 0, RX 0 |

## Interpretation boundary

This proves a safe independent transport lifecycle. It does not prove the full
application protocol, session authentication, media channels, or permission to
send stock commands.

## Stock message observation

A separate four-action stock Developer Mode capture established a bounded
outbound frame grammar. Custom sending and captured replay remain unimplemented
and prohibited.

## Authoritative detail

- [Connection-protocol index](../research/connection-protocol/README.md)
- [Stock ADB-toggle publication](../research/connection-protocol/stock-adb-toggle/README.md)
