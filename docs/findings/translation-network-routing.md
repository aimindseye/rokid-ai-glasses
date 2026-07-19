# Translation Network Routing

## Online provider observed

The tested Online translation configuration used Microsoft Azure Speech.

Observed service families included:

- `centralus.api.cognitive.microsoft.com`
- `centralus.stt.speech.microsoft.com`
- `centralus.tts.speech.microsoft.com`

Application logs identified Azure translation execution and an Azure Spanish
neural voice.

## Session support

Passive connection evidence also included real-time session infrastructure:

- `edge.agora.io`
- `ap.rtnsvc.com`

These hosts are documented as observed support infrastructure. Their exact
per-packet role was not fully reconstructed.

## Rokid control plane

Rokid application endpoints remained part of session setup and control.
Observing Azure speech services does not imply that the companion application
bypasses Rokid's backend entirely.

## ChatGPT/Gemini selector

Changing the assistant base-model label between ChatGPT and Gemini did not
produce a detectable change in the online translation service path.

No direct OpenAI or Google model endpoint was observed for translation.
This is specific to translation and must not be generalized to all assistant
requests.

## TLS behavior

PCAPdroid TLS interception caused a translation service error, while passive
capture succeeded.

That difference establishes interception sensitivity. It does not by itself
prove a specific pinning library or certificate-validation implementation.

## Local-mode network result

Local recognition and translation succeeded while:

- Wi-Fi was disabled,
- mobile data was disabled,
- Bluetooth remained active,
- direct reachability failed, and
- Rokid hostname resolution failed.

After the Android Spanish offline voice was installed, Local spoken output
also completed without network access.
