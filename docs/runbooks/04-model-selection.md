# Runbook 04 — Base-Model Selection

## Preconditions

- Test-account session rotated after Test 03b
- Glasses connected normally
- Background execution remains disabled
- Offline translation model remains undownloaded
- PCAPdroid TLS decryption enabled for Hi Rokid
- QUIC blocked
- adb logcat running to a test-specific private file
- No prompt or image submitted

## 04a — Gemini base-model selection

Change only the base model to Gemini. Leave the vision model unchanged.
Capture for 60–90 seconds after the selection and then stop.

Private artifacts:

- PCAP
- SSL keylog
- PCAPdroid CSV
- adb logcat
- decrypted HTTP request inventory
- WebSocket frame export
- SHA-256 manifest

## 04b — ChatGPT base-model selection

Repeat the same procedure, changing only the base model to ChatGPT.

## Comparison questions

- Does the selection produce a REST preference update?
- Does `/ws/ai` receive a model-change message?
- Does the AI WebSocket reconnect?
- Does an internal model ID change?
- Does any new hostname appear?
- Is the selection stored locally, server-side, or both?

Do not submit a prompt until 04a and 04b have been compared.
