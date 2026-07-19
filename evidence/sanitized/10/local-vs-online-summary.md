# Test 10 Local-versus-Online Summary

## Control

Both phases used:

- Face to Face,
- English to Spanish,
- the same generated source-audio file,
- the same phone and glasses, and
- the same placement.

Source-audio SHA-256:

```text
96517defec508647637864b841c68c477f7629589d80108580bd43be2d4f04cc
```

## Architecture comparison

| Stage | Local | Online |
|---|---|---|
| Input | Glasses microphone | Glasses microphone |
| Recognition/translation | Phone-side `wend` | Microsoft Azure Speech |
| TTS | Google Android offline voice | Azure neural voice |
| Output | Bluetooth A2DP to glasses | Bluetooth A2DP to glasses |
| Internet | Not required after voice install | Required |

## Behavioral result

Both modes emitted progressive text updates and synthesized speech after a
final segment.

The test intentionally did not evaluate translation accuracy or acoustic
quality.
