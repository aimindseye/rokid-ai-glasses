# Test 04 — Base-Model Selection

## Purpose

Determine whether changing the Hi Rokid base-model selection produces an
immediate observable network, WebSocket, Bluetooth, or application-log
update before any prompt is submitted.

The tests intentionally do not attempt provider attribution. A selectable
ChatGPT or Gemini label proves only that the option exists in the UI.

## Controls

Both tests used the same controlled account, phone profile, Hi Rokid
package, glasses connection, capture configuration, and background setting.

Common controls:

- Package: `com.rokid.sprite.global.aiapp`
- App version: `G1.10.11.0713`
- Android secondary user: 10
- PCAPdroid app filter: Hi Rokid only
- TLS interception enabled
- QUIC blocked
- Background execution disabled
- Offline translation model undownloaded
- No text prompt submitted
- No image or vision request submitted
- Only the base model changed
- Vision model remained Gemini

Raw PCAP, TLS keylog, WebSocket payloads, logcat, screenshots, and CSV
exports remain private.

## Test 04a — ChatGPT to Gemini

### Controlled state

- Before: base ChatGPT, vision Gemini
- After: base Gemini, vision Gemini

### Validity

`VALID WITH OPERATOR MARKER CORRECTION`

A valid `ACTION_START` marker was recorded before selection. A second
`ACTION_START` was entered after the selection by operator mistake, and the
final-state confirmation marker followed later. The private normalized
timeline preserves the correction and bounds the action window.

### Network result

- The AI WebSocket and model-catalog requests occurred before selection
- No dedicated HTTP request accompanied the selection
- No additional or out-of-cadence WebSocket message accompanied the
  selection
- Small client binary messages retained an approximately ten-second cadence
- The exact selection-window request and response matched the existing
  periodic message family

### WebSocket persistence result

The first same-length post-selection messages differed at a few byte
positions that had been stable in a limited pre-selection baseline.
Persistence analysis showed:

- Positions 29 and 41 changed persistently but carried varying new values
- Position 44 changed intermittently
- No changed position retained one constant new value across all
  post-selection messages

That pattern is consistent with ordinary heartbeat metadata such as
timestamps, counters, nonces, or request identifiers. It does not identify
a stable Gemini-selection field.

### Log result

No explicit Gemini, ChatGPT, model ID, preference update, WebSocket send,
GATT write, RFCOMM write, or Bluetooth write associated with the selection
was identified in available logcat.

Absence from logcat does not prove that no local update occurred.

## Test 04b — Gemini to ChatGPT

### Controlled state

- Before: base Gemini, vision Gemini
- After: base ChatGPT, vision Gemini

### Validity

`VALID`

Exactly one marker of each required type was recorded:

- `BEGIN`
- `ACTION_START`
- `ACTION_COMPLETE`
- `END`

### Network result

- `/ws/ai` and both model-aggregate requests occurred before selection
- No HTTP request occurred during the selection window
- No HTTP request occurred during the post-selection observation period
- No additional or out-of-cadence WebSocket message accompanied selection
- The WebSocket did not reconnect because of selection
- Small client messages had a median interval of approximately 10.005
  seconds, with an observed range of 10.000 through 10.007 seconds

### WebSocket persistence result

For the regular periodic message families:

| Direction | Length | Baseline | Selection | Post-selection | Stable positions changed |
|---|---:|---:|---:|---:|---:|
| Client to server | 54 | 5 | 2 | 8 | 0 |
| Server to client | 109 | 5 | 2 | 8 | 0 |

No constant, variable, or intermittent change was observed at any byte
position that had been stable throughout the corresponding baseline.

### Log result

No explicit Gemini, ChatGPT, model ID, preference update, WebSocket send,
GATT write, RFCOMM write, or Bluetooth write associated with the selection
was identified in available logcat.

Unrelated Android Messages `BugleDataModel` records were excluded from the
Hi Rokid interpretation.

### Screenshot recovery

The original streamed screenshot files contained a 347-byte Android
multiple-display warning before the PNG stream. The originals remain
private and unchanged.

The embedded PNGs were extracted by locating the PNG signature, parsing
chunks through IEND, and validating every chunk CRC. Both recovered images
had zero CRC failures and decoded as 1080-by-2640, 8-bit RGBA PNGs.

## Bidirectional comparison

| Observation | 04a: ChatGPT to Gemini | 04b: Gemini to ChatGPT |
|---|---|---|
| UI transition confirmed | Yes | Yes |
| Dedicated HTTP selection request | Not identified | Not identified |
| Additional WebSocket message | Not identified | Not identified |
| Selection-associated reconnect | Not identified | Not identified |
| Constant persistent WebSocket field | Not identified | Not identified |
| Relevant model-selection logcat event | Not identified | Not identified |
| Test validity | Valid with marker correction | Valid |

## Interpretation

Changing the base model in either direction did not produce an identifiable
immediate cloud-side update in the observed HTTP, WebSocket, or logcat
evidence.

The selected model may be stored locally, applied when an assistant session
starts, or transmitted through a mechanism not visible in the collected
evidence. Local storage or deferred application is plausible, not proven.

These tests do not establish whether a later Gemini- or ChatGPT-labeled
prompt is processed directly by Google, OpenAI, another provider, or a
Rokid-managed intermediary.

## Next test

Test 05b submits a unique ChatGPT text canary while preserving ChatGPT as
the selected base model. Model selection must not be changed in the same
capture.
