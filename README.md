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

Validated as of 2026-07-16:

- Hi Rokid package identified as `com.rokid.sprite.global.aiapp`
- Pre-login and post-login network baselines captured
- Owner-authorized account transfer documented
- BLE, GATT, classic Bluetooth, and RFCOMM use observed
- PCAPdroid TLS interception validated
- Rokid HTTP/1.1, HTTP/2, JSON, and WebSocket traffic decrypted
- Rokid model catalog and AI WebSocket gateway identified

Model-specific prompt and vision-routing tests are not yet complete.

## Evidence policy

Raw captures and credentials are not stored in this public repository.

Public evidence is limited to:

- Sanitized endpoint inventories
- Redacted protocol summaries
- Test methodology
- Evidence hashes
- Sanitized screenshots and excerpts

Raw PCAP files, TLS key logs, Android bugreports, logcat files, tokens,
account identifiers, device serial numbers, and decrypted payloads remain
outside the Git worktree.

See [Evidence Handling](docs/methodology/evidence-handling.md).

## Repository layout

- `docs/methodology/` — test and evidence-handling procedures
- `docs/tests/` — individual test reports
- `docs/findings/` — consolidated technical findings
- `evidence/sanitized/` — reviewed public evidence
- `evidence/manifests/` — hashes and provenance records
- `scripts/` — extraction, sanitization, and validation tools

## Disclaimer

This project is not affiliated with Rokid. Testing is performed only on
devices and accounts controlled by the repository owner.
