# Runbook 04 — Base-Model Selection

## Execution status

Executed on 2026-07-17.

- 04a: ChatGPT base model to Gemini base model
- 04b: Gemini base model to ChatGPT base model
- Vision model remained Gemini throughout both tests
- No prompt, image, or vision operation was submitted
- Background execution remained disabled
- Offline translation data remained undownloaded

## Preconditions used

- Test-account session active after the Test 03b security-handling step
- Glasses connected normally
- Background execution disabled
- Offline translation model undownloaded
- PCAPdroid TLS decryption enabled for Hi Rokid
- QUIC blocked
- adb logcat recorded to test-specific private files
- Before-state and after-state UI evidence preserved privately
- Model selection kept separate from prompt submission

## 04a — Gemini base-model selection

Controlled transition:

- Before: base ChatGPT, vision Gemini
- After: base Gemini, vision Gemini

Result:

- Accepted as `VALID WITH OPERATOR MARKER CORRECTION`
- A duplicate `ACTION_START` marker was entered after the selection
- The normalized action timeline bounds the selection between the valid
  pre-action marker and the duplicate marker
- No dedicated HTTP selection request was identified
- No additional or out-of-cadence WebSocket message was identified
- Post-selection byte differences were variable or intermittent rather than
  a constant persistent new value
- No relevant model preference, model ID, WebSocket-send, GATT, RFCOMM, or
  Bluetooth-write event was identified in available logcat

## 04b — ChatGPT base-model selection

Controlled transition:

- Before: base Gemini, vision Gemini
- After: base ChatGPT, vision Gemini

Result:

- Accepted as `VALID`
- Exactly one `BEGIN`, `ACTION_START`, `ACTION_COMPLETE`, and `END` marker
  was recorded
- No HTTP request occurred during or after the selection
- WebSocket small-message cadence remained approximately ten seconds
- No additional or out-of-cadence WebSocket message was identified
- For the 54-byte client family and 109-byte server family, all byte
  positions stable across five baseline frames remained unchanged across
  two selection-window frames and eight post-selection frames
- No relevant model preference, model ID, WebSocket-send, GATT, RFCOMM, or
  Bluetooth-write event was identified in available logcat

## Screenshot handling

The 04b streamed screenshots contained a 347-byte Android multiple-display
warning before the PNG signature. The original source streams remain
private and unchanged. The embedded PNGs were extracted through the IEND
chunk, validated with zero PNG chunk CRC failures, and confirmed as
1080-by-2640 RGBA images.

## Comparison answers

### Did selection produce a REST preference update?

No identifiable REST or HTTP preference update occurred during either
selection.

### Did `/ws/ai` receive a dedicated model-change message?

No additional or out-of-cadence WebSocket message was identified.

### Did the AI WebSocket reconnect?

No selection-associated reconnect was identified.

### Did a persistent internal model field change?

No constant persistent post-selection field was identified in 04a. In 04b,
no previously stable position changed in the analyzed 54-byte client and
109-byte server message families.

### Did a new hostname appear?

No selection-specific hostname was identified.

### Is the selection stored locally, server-side, or both?

The evidence supports local storage or deferred application as plausible
explanations, but does not prove either mechanism. A value could also be
transmitted later when an assistant session begins or through an
unobserved mechanism.

## Next gate

Do not infer upstream provider routing from the UI labels. Test 05b must
change only one variable by submitting the ChatGPT text canary while
preserving the current ChatGPT base-model state.
