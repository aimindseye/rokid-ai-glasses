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

Validated through Test 03b:

- Hi Rokid package identified as `com.rokid.sprite.global.aiapp`
- Pre-login and post-login network baselines captured
- Owner-authorized unbind, account change, and rebind documented
- BLE, GATT, classic Bluetooth, and RFCOMM use observed
- PCAPdroid TLS interception validated with a unique Firefox HTTPS canary
- Hi Rokid HTTP/1.1, HTTP/2, JSON, and WebSocket traffic decrypted
- Rokid model-catalog and AI WebSocket gateway endpoints identified

Model-selection-only tests and prompt-routing tests remain pending.

## Evidence policy

Raw captures and credentials are not stored in this public repository. Public
evidence is limited to sanitized endpoint inventories, protocol summaries,
methodology, hash-only manifests, and reviewed redacted excerpts.

Raw PCAP files, TLS key logs, bugreports, logcat files, tokens, account IDs,
device serials, Bluetooth addresses, and decrypted payloads remain outside the
Git worktree.

See [Evidence Handling](docs/methodology/evidence-handling.md).

## Documentation

- [Test methodology](docs/methodology/test-methodology.md)
- [Test matrix](docs/tests/test-matrix.md)
- [TLS interception baseline](docs/tests/03-tls-interception.md)
- [Endpoint inventory](docs/findings/endpoint-inventory.md)
- [Security and privacy observations](docs/findings/security-and-privacy-observations.md)
- [Next model-selection runbook](docs/runbooks/04-model-selection.md)

## Repository layout

- `docs/methodology/` — test and evidence-handling procedures
- `docs/tests/` — completed test reports and matrix
- `docs/runbooks/` — controlled procedures for pending tests
- `docs/findings/` — consolidated technical findings
- `evidence/sanitized/` — reviewed public evidence
- `evidence/manifests/` — hash-only provenance records
- `scripts/` — extraction, sanitization, and validation tools

## Disclaimer

This project is not affiliated with Rokid. Testing is performed only on
devices and accounts controlled by the repository owner.
