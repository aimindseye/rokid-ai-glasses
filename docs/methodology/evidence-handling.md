# Evidence Handling

## Public/private boundary

Private evidence may contain:

- packet captures and TLS secrets;
- account and session identifiers;
- device identifiers and Bluetooth addresses;
- precise location or context;
- authorization headers and signatures;
- raw logcat, bugreports, screenshots, and UI dumps;
- APK/native-library analysis artifacts;
- ADB host keys and authorized-host files;
- raw USB/configfs metadata and stable USB/ADB serials;
- block-device maps and boot, vbmeta, vendor, or other partition images.

Private evidence remains outside the Git worktree.

## Public evidence allowed

The repository may contain:

- sanitized reports;
- generalized endpoint and protocol summaries;
- reproducible capture scripts;
- cropped images without private data;
- redacted excerpts;
- hash-only manifests;
- synthetic fixtures.

## Privacy-first test output

Test 16B–16D scripts create two separate trees:

```text
private-raw-DO-NOT-UPLOAD/
sanitized-upload/
```

Only the privacy-gated `-SANITIZED-UPLOAD.zip` is suitable for review. The
sanitizer preserves hostnames, path templates, event types, counts, hashes, and
sensitive-field **presence/value state** while excluding the underlying
identifiers, coordinates, credentials, tokens, audio, images, and payload
values.

A local HMAC key can correlate pseudonymous package/UID identities across runs
without publishing the originals. The key remains outside the repository.

## Review procedure

Before publication:

1. inspect every file;
2. remove workstation paths and identifiers;
3. remove tokens, signatures, cookies, and authorization values;
4. confirm screenshots contain no account/device information;
5. exclude raw captures and TLS keys;
6. generate hashes for private provenance when useful;
7. run `scripts/safety/validate_public_repo.sh`.

## Hash-only provenance

A private-bundle SHA-256 shows which private evidence supported a public report
without publishing its contents. A hash does not make private evidence public
and does not prove the report by itself.

## Repository safety gate

The CI gate rejects common raw-capture, TLS-key, APK, native-library, and
bugreport file types. It also checks for known private path/serial patterns and
compiles the public Python tools.


## Test 17 ADB and glasses-OS evidence

Test 17 uses a stricter glasses-development boundary:

- device serials and ADB host keys remain private;
- selected APKs may be pulled only into the private evidence tree;
- public evidence may include package names and SHA-256 hashes, not binaries;
- raw `dumpsys`, package, Binder, HAL, process, listener, init, USB, interface,
  and log output remains private;
- only high-level storage/mount conclusions are public;
- no block-device map or partition image is public;
- no request is sent to an unexplained local listener.

The Test 17F collector creates separate private and sanitized trees and runs a
privacy gate before presenting the public summary. The public repository stores
a consolidated assertion set and a hash-only provenance manifest rather than
the raw collector output.
