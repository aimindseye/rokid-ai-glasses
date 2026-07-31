# Platform Security and Privacy

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Required controls

- phone-bound user identity and explicit device ownership;
- mutual TLS or equivalent authenticated encryption;
- least-privilege device and Android permissions;
- no public-cloud fallback without explicit policy;
- no raw photo or audio retention by default;
- encrypted, bounded retry buffers;
- RBAC propagated to structured, graph, RAG, and model layers;
- immutable request, evidence, decision, response, and error lineage;
- prompt-injection handling for text visible in captured images;
- fail-closed behavior when evidence or authorization is unavailable.

## Spoken-output risk

Open-ear audio can disclose sensitive results to nearby people. Production
workflows should support short answers, earcons, redaction, phone confirmation,
and a policy that routes highly sensitive detail to the phone rather than
speaking it automatically.

## Development evidence handling

Keep raw PCAPs, TLS secrets, bugreports, HCI logs, APKs, native libraries,
decrypted exports, serials, Bluetooth addresses, and precise location private.
Publish only sanitized summaries, hashes, and tooling that operates on already
sanitized inputs.
