# Test 10c3 — Offline Local Execution

## Status

Complete — PASS AFTER TARGET-LANGUAGE OFFLINE VOICE INSTALL.

## Question

Can the downloaded local stack execute without usable internet, and what
component supplies spoken translated output?

## Offline control

The companion phone was placed in a controlled offline state:

- Wi-Fi disabled,
- mobile data disabled,
- Bluetooth preserved,
- Hi Rokid force-stopped after the network change,
- no default route available,
- direct reachability failed, and
- Rokid hostname resolution failed.

The glasses remained connected over Bluetooth.

## Local execution

Hi Rokid successfully:

1. loaded the phone-side `wend` package,
2. started offline recording,
3. consumed audio from the glasses,
4. ran local speech encoding and transcription,
5. produced a local Spanish translation, and
6. submitted the final text for speech synthesis.

This proves that recognition and translation were not dependent on the
Microsoft online path in this run.

## First TTS attempt

The first offline run did not produce spoken Spanish. Android's Google speech
engine had no Spanish offline model installed, selected a network-backed
voice, and failed while the phone was offline.

This failure was useful because it separated the local translation model
from the speech-synthesis dependency.

## Repeat after voice installation

After installing the Spanish (Spain) offline voice:

- Android selected a local embedded Spanish voice,
- local synthesis completed,
- playback completed, and
- audio was routed through Bluetooth A2DP to the glasses.

## Confirmed Local path

```text
glasses microphone
-> phone-side VAD and speech encoder
-> phone-side Qwen3 translation
-> Android Google offline TTS
-> Bluetooth A2DP
-> glasses speakers
```

## Result

Local recognition and translation can operate without usable internet on the
compatible phone.

End-to-end offline spoken translation additionally requires the target
language's Android offline TTS voice. The `wend` package alone is not a
complete speech-synthesis stack.

## Boundary

The fixed phrase was used only to prove execution flow. This test does not
score translation accuracy or voice quality.
