# Public Evidence

This directory contains only reviewed and sanitized evidence.

Raw network captures, TLS keys, decrypted payloads, Android logs, Bluetooth
captures, account identifiers, and device identifiers are intentionally
excluded.

## Current evidence

### `sanitized/03b/protocol-summary.txt`

Protocol hierarchy for the Hi Rokid TLS interception test covering application
startup, connected-device initialization, model-management navigation, and
idle behavior.

The summary establishes the presence of:

- DNS
- TLS
- HTTP/1.1
- HTTP/2
- JSON
- WebSocket traffic

It does not contain request headers, credentials, account identifiers, device
serial numbers, or message bodies.
