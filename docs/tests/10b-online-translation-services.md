# Test 10b — Online Translation Services

## Status

Complete — PASS WITH CAPTURE CAVEATS.

## Question

Which infrastructure supports Online speech translation, and does selecting
ChatGPT or Gemini as the assistant base model change that path?

## Method

- Use Face-to-Face translation.
- Keep English-to-Spanish direction constant.
- Run controlled trials with ChatGPT and Gemini selected.
- Use passive PCAPdroid capture and application logs.
- Treat TLS-intercepted runs as diagnostic only when interception changes
  application behavior.

## TLS-interception control

Translation produced a service error while PCAPdroid TLS interception was
enabled. Passive capture with TLS decryption disabled worked.

The selective failure is consistent with a native trust, certificate-pinning,
or SDK-specific TLS constraint. The available evidence does not distinguish
among those mechanisms, so no narrower claim is made.

## Observed service families

| Role | Observed hostname or family |
|---|---|
| Azure configuration/translation | `centralus.api.cognitive.microsoft.com` |
| Speech recognition | `centralus.stt.speech.microsoft.com` |
| Neural text-to-speech | `centralus.tts.speech.microsoft.com` |
| Real-time session support | `edge.agora.io` |
| Real-time service support | `ap.rtnsvc.com` |
| Rokid control/backend | Rokid application service endpoints |

Application logs identified Azure translation execution in the `centralus`
region and an Azure Spanish neural voice.

## Assistant-model comparison

Both ChatGPT-selected and Gemini-selected translation trials used the same
Microsoft Azure Speech infrastructure. No direct OpenAI or Google model
endpoint was observed for the translation workflow.

This establishes that the tested assistant selector did not visibly alter the
translation backend. It does not establish how Rokid routes general assistant
prompts or whether an upstream provider is used behind other Rokid services.

## Capture caveats

The final minimal run was sufficient for architecture identification but was
not a clean latency or accuracy benchmark:

- one ChatGPT trial included a repeated phrase,
- one Gemini setup initially used the wrong target language before correction,
- only the corrected successful segments were used for architecture findings.

## Result

The tested Online path was:

```text
glasses microphone
-> companion application
-> Microsoft Azure Speech recognition and translation
-> Azure neural TTS
-> Bluetooth A2DP
-> glasses speakers
```
