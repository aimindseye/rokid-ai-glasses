# Controlled Voice Canary Method

This method captures one assistant interaction while preserving enough timing and transport context for later comparison.

## Scope

The protocol is intended to answer narrow questions such as:

- Which phone-visible host and WebSocket path carried the interaction?
- Did the application expose interim and normalized ASR states?
- Did controlled prompt or response phrases appear inside decrypted application records?
- Did two captures differ at the application-protocol layer?

It does not establish the identity of an upstream model provider unless a direct provider endpoint or independently decoded routing field is observed.

## Standardized interaction

Use one short spoken request exactly once. Record the model-selection UI before and after the capture. Do not retry or continue the conversation.

Recommended marker order:

1. `BEGIN`
2. `VOICE_READY`
3. `ACTION_START`
4. `ACTION_COMPLETE`
5. `RESPONSE_START`
6. `RESPONSE_COMPLETE`
7. `END`

Use the marker controller in `scripts/capture/run_voice_marker_controller.py`. Marker timestamps are operator observations, not model latency measurements.

## Validity conditions

A controlled capture should have:

- one assistant invocation;
- one spoken request;
- no retries or additional conversation;
- no capture restart;
- selected-model screenshots before and after;
- a complete marker sequence;
- private PCAP, TLS key log, connection export, and logcat artifacts;
- a private evidence manifest that verifies successfully.

## Analysis sequence

1. Export WebSocket payload occurrences with actual decoded lengths.
2. Search only allowlisted controlled phrases.
3. Summarize traffic by marker window, direction, and opcode.
4. Compare sanitized JSON summaries rather than raw evidence.
5. Publish only sanitized conclusions and report hashes.
