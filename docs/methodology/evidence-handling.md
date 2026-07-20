# Evidence Handling

## Public/private boundary

Private evidence may contain:

- packet captures and TLS secrets;
- account and session identifiers;
- device identifiers and Bluetooth addresses;
- precise location or context;
- authorization headers and signatures;
- raw logcat, bugreports, screenshots, and UI dumps;
- APK/native-library analysis artifacts.

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
