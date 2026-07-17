# Rokid AI Glasses Research

Independent technical research into the Rokid AI Glasses and the Hi Rokid
Android application.

## Scope

This repository documents:

- Android application behavior
- Network endpoints and protocol usage
- Bluetooth pairing and device binding
- TLS interception methodology
- ChatGPT and Gemini model-routing tests
- Privacy and security observations

## Current status

Validated through Test 04b:

- Hi Rokid package identified as `com.rokid.sprite.global.aiapp`
- Pre-login and post-login network baselines captured
- Owner-authorized unbind, account change, and rebind documented
- BLE, GATT, classic Bluetooth, and RFCOMM use observed
- PCAPdroid TLS interception validated with a unique Firefox HTTPS canary
- Hi Rokid HTTP/1.1, HTTP/2, JSON, and WebSocket traffic decrypted
- Rokid model-catalog and AI WebSocket gateway endpoints identified
- Bidirectional base-model selection tests completed:
  ChatGPT to Gemini in 04a and Gemini to ChatGPT in 04b
- Neither selection produced an identifiable immediate HTTP update,
  additional WebSocket message, WebSocket reconnect, or persistent
  WebSocket model-state field
- Test 04a is accepted with a documented operator-marker correction;
  Test 04b is accepted without a marker correction

Text-canary prompt-routing tests are next. The current controlled state is
ChatGPT as the base model and Gemini as the vision model, so Test 05b is the
next planned capture.

## Evidence policy

Raw captures and credentials are not stored in this public repository.
Public evidence is limited to sanitized endpoint inventories, protocol
summaries, methodology, hash-only manifests, and reviewed redacted excerpts.

Raw PCAP files, TLS key logs, bugreports, logcat files, tokens, account IDs,
device serials, Bluetooth addresses, screenshots, and decrypted payloads
remain outside the Git worktree.

See [Evidence Handling](docs/methodology/evidence-handling.md).

## Documentation

- [Test methodology](docs/methodology/test-methodology.md)
- [Test matrix](docs/tests/test-matrix.md)
- [TLS interception baseline](docs/tests/03-tls-interception.md)
- [Base-model selection tests](docs/tests/04-model-selection.md)
- [Endpoint inventory](docs/findings/endpoint-inventory.md)
- [Model-selection behavior](docs/findings/model-selection-behavior.md)
- [Security and privacy observations](docs/findings/security-and-privacy-observations.md)
- [Executed model-selection runbook](docs/runbooks/04-model-selection.md)

## Repository layout

- `docs/methodology/` — test and evidence-handling procedures
- `docs/tests/` — completed test reports and matrix
- `docs/runbooks/` — controlled procedures and execution records
- `docs/findings/` — consolidated technical findings
- `evidence/sanitized/` — reviewed public evidence
- `evidence/manifests/` — hash-only provenance records
- `scripts/` — extraction, sanitization, manifest, and validation tools

## Disclaimer

This project is not affiliated with Rokid.

Testing is performed only on devices and accounts controlled by the
repository owner.
