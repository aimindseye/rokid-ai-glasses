# Test 10 Online Endpoint Summary

## Microsoft Azure Speech

| Function | Observed hostname or family |
|---|---|
| Translation configuration/API | `centralus.api.cognitive.microsoft.com` |
| Speech recognition | `centralus.stt.speech.microsoft.com` |
| Text-to-speech | `centralus.tts.speech.microsoft.com` |

Application execution logs independently identified Azure translation and an
Azure Spanish neural voice.

## Real-time support infrastructure

- `edge.agora.io`
- `ap.rtnsvc.com`

These were observed during translation sessions. The public evidence does not
assign a narrower packet-level function.

## Rokid infrastructure

Rokid application service endpoints remained involved in session and control
behavior. Raw endpoint inventories and payloads remain private.

## Model-selector result

ChatGPT-selected and Gemini-selected Online translation trials used the same
observed Microsoft service families.

No direct OpenAI or Google model endpoint was observed for the tested
translation path.

## TLS caveat

Translation failed under the tested MITM configuration and succeeded under
passive capture. The evidence establishes interception sensitivity but does
not identify the exact native TLS or pinning mechanism.
