# Public Evidence

This directory contains only reviewed and sanitized evidence.

Raw packet captures, TLS keys, decrypted payloads, Android logs, Bluetooth
captures, account IDs, device IDs, credentials, model binaries, and
screenshots are intentionally excluded.

## Test 03b

`sanitized/03b/` contains protocol and aggregated connection summaries.

`manifests/03b-private-evidence-sha256.json` contains hashes, sizes, and
private-relative filenames only.

## Tests 04a and 04b

`sanitized/04/model-selection-summary.md` contains the reviewed
bidirectional model-selection result without raw payload bytes, identifiers,
or private paths.

The hash-only provenance files are:

- `manifests/04a-private-evidence-sha256.json`
- `manifests/04b-private-evidence-sha256.json`

## Test 10

`sanitized/10/` contains:

- `README.md` — public evidence index
- `endpoint-summary.md` — online translation service families
- `local-model-metadata.md` — package inventory and bounded model metadata
- `offline-execution-summary.md` — offline processing and TTS dependency
- `local-vs-online-summary.md` — controlled architecture comparison

`manifests/10-private-evidence-sha256.json` contains archive names, sizes,
SHA-256 digests, public-test mappings, and the `private-hash-only`
classification. It contains no raw capture content.
