# Test 10 — Translation Overview

## Status

Complete through Test 10c4.

## Objective

Determine how Hi Rokid speech translation operates, specifically:

- which microphone supplies Face-to-Face translation,
- where Local processing runs,
- what the downloaded local package contains,
- whether Local mode can operate without usable internet,
- which component supplies Local spoken output,
- which services support Online mode,
- how audio is returned to the glasses, and
- whether ChatGPT/Gemini assistant selection changes the translation path.

This series is an architecture and execution-flow investigation. It is not a
translation-accuracy, voice-quality, or production-performance benchmark.

## Public numbering and private capture aliases

| Public ID | Private capture alias | Purpose |
|---|---|---|
| 10a | translation routing preflight plus 07c runtime logs | Face-to-Face microphone and playback route |
| 10b | 07b | Online translation service routing |
| 10c1 | 07c-1 | Local-model download provenance |
| 10c2 | 07c-2 | Installed local-package analysis |
| 10c3 | 07c-3 | Offline execution and TTS dependency |
| 10c4 | 07c-4 | Controlled Local-versus-Online flow |

Private archives remain outside Git. Their SHA-256 digests and sizes are
recorded in
[`evidence/manifests/10-private-evidence-sha256.json`](../../evidence/manifests/10-private-evidence-sha256.json).

## Environment

- Hi Rokid: `G1.10.11.0713`
- Android package: `com.rokid.sprite.global.aiapp`
- Compatible companion: Samsung flagship phone
- Glasses: display-free Rokid AI Glasses
- Translation profile: Face to Face
- Controlled language direction: English to Spanish
- Local package: `wend` `v2.7.0`

Raw serials, account identifiers, Bluetooth addresses, exact locations, and
private paths are intentionally omitted.

## Results

### Input and output routing

Application logs reported an audio listener from the glasses while Face to
Face was active. System audio state showed translated speech routed through
Bluetooth A2DP to the glasses.

### Online mode

The tested Online path used Microsoft Azure Speech infrastructure for speech
recognition, translation, and neural TTS. ChatGPT/Gemini assistant selection
did not produce a detectable change in that translation infrastructure.

### Local package

The compatible phone downloaded a Rokid-hosted `wend` package. The installed
package contains:

- a streaming VAD,
- a quantized speech encoder,
- a Qwen3 text model, and
- metadata/configuration files.

No identifiable TTS or vocoder model was present.

### Offline execution

With Wi-Fi and mobile data disabled, Hi Rokid loaded `wend`, consumed the
glasses audio stream, produced translated text, and attempted spoken output.

The first run exposed an external dependency: the Android speech engine did
not have the Spanish offline voice installed and attempted a network-backed
voice. After installing the Spanish offline voice, local TTS completed and
played through the glasses while the phone remained offline.

### Controlled Local-versus-Online comparison

The final comparison kept Face to Face, English-to-Spanish direction, source
audio, phone, glasses, and placement constant.

| Stage | Local | Online |
|---|---|---|
| Input | Glasses microphone | Glasses microphone |
| Processing host | Companion phone | Microsoft-hosted speech service |
| Recognition/translation | `wend` local stack | Azure Speech |
| Spoken output | Google Android offline TTS | Azure neural TTS |
| Return route | Bluetooth A2DP to glasses | Bluetooth A2DP to glasses |
| Internet requirement | No, after offline voice install | Yes |

Both modes produced progressive text updates before a final segment. Spoken
output followed the final segment rather than speaking every partial update.

## Main conclusion

The glasses function as the wearable audio endpoint, while the companion
phone is the translation control and processing host.

Local mode runs the downloaded speech-and-language stack on the phone and
delegates speech synthesis to the installed Android TTS engine. Online mode
sends the speech workflow through Microsoft Azure Speech in the tested
configuration.

## Boundaries

- One fixed phrase was used as a flow canary, not an accuracy benchmark.
- No acoustic recording was used to compare voice quality.
- The Azure result is version-, region-, and configuration-specific.
- Selective failure under TLS interception does not by itself distinguish
  certificate pinning from native trust-store or SDK-specific TLS behavior.
- The exact upstream checkpoint behind the quantized speech encoder was not
  established.
