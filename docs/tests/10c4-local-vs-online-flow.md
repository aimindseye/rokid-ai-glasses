# Test 10c4 — Controlled Local-versus-Online Flow

## Status

Complete — PASS.

## Objective

Compare how speech translation operates in Local and Online modes without
turning the run into an accuracy or acoustic-quality benchmark.

## Controlled variables

Both phases used:

- Face to Face,
- English to Spanish,
- the same glasses and companion phone,
- the same placement,
- the same generated source-audio file, and
- the same fixed phrase.

The source-audio SHA-256 was:

```text
96517defec508647637864b841c68c477f7629589d80108580bd43be2d4f04cc
```

No external output recording was used.

## Changed variable

Only the processing mode and its required network state changed:

- Local: Wi-Fi and mobile data disabled
- Online: functional internet restored

## Result

| Stage | Local | Online |
|---|---|---|
| Audio source | Glasses microphone | Glasses microphone |
| Companion role | Processing host and control plane | Control plane and service client |
| Recognition/translation | `wend` local stack | Microsoft Azure Speech |
| Text-to-speech | Google Android offline TTS | Azure neural TTS |
| Audio output | Bluetooth A2DP to glasses | Bluetooth A2DP to glasses |
| Internet | Not required after voice install | Required |

## Streaming behavior

Both paths behaved as segmented streaming translation:

1. audio frames arrived from the glasses,
2. partial text was updated,
3. a final segment was produced,
4. TTS was queued for the final segment, and
5. translated speech was played through the glasses.

The observed design is not word-by-word simultaneous spoken interpretation.
Text updates are progressive, but speech synthesis follows a completed
segment.

## Android policy-routing note

The original automation briefly treated the absence of a `default` line in
the main `ip route` output as an Online failure. The phone had working
internet through an Android policy-routing table.

Future checks must inspect all routing tables or verify functional
reachability instead of relying only on the main table.

## Scope boundary

The run establishes architecture, network dependency, engine selection, and
audio route. It does not compare translation quality, TTS naturalness, or
production latency.
