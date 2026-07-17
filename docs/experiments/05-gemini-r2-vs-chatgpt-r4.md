# Gemini-Selected vs. ChatGPT-Selected Voice Canary

## Status

Controlled comparative observation using the Hi Rokid Android application.

Compared captures:

- `05a-gemini-voice-canary-r2`
- `05b-chatgpt-voice-canary-r4`

Each capture used one spoken request:

> Say blue apple seven.

The selected base model was verified in the Hi Rokid UI before and after each capture.

## Phone-visible transport

Both captures used the same phone-visible AI transport:

- Host: `ai-cloud-global.rokid.com`
- Path: `/ws/ai`
- Protocol: binary WebSocket application records

No direct OpenAI or Google Gemini endpoint was observed from the phone.

The captures therefore establish communication with the Rokid AI gateway, not direct communication with either named model provider.

## Occurrence-aware WebSocket totals

Payload sizes were calculated from decoded `websocket.payload` occurrences. The WebSocket extended-length marker value `126` was not treated as an actual payload length.

| Measurement | ChatGPT-selected r4 | Gemini-selected r2 |
|---|---:|---:|
| WebSocket payload records | 454 | 435 |
| Client-to-server payload bytes | 204,360 | 219,885 |
| Server-to-client payload bytes | 63,593 | 113,041 |
| Total payload bytes | 267,953 | 332,926 |
| Prompt-bearing records | 2 | 2 |
| Tested plaintext response-bearing records | 0 | 2 |
| Prompt-state separation | 0.226 s | 0.510 s |

Gemini carried 7.6% more client-to-server payload bytes, 77.8% more server-to-client payload bytes, and 24.2% more total payload bytes in these complete captures.

These totals are descriptive. They are not efficiency, latency, or model-performance measurements because the capture durations, marker protocols, response wording, and post-response recording periods differed.

## ASR behavior

Both captures exposed two downstream transcript-bearing binary records.

The observed sequence in each capture was consistent with:

1. A lowercase or minimally normalized transcript.
2. A capitalized and punctuated transcript.

This supports an interim/raw to normalized/final ASR interpretation, although no explicit final-state protocol field has been decoded.

## Gemini-selected response behavior

The Gemini-selected capture exposed its observed response in two ordered downstream binary records.

The first identifiable response fragment arrived:

- 1.921 seconds after the final transcript-bearing record.
- 1.724 seconds before the first operator-observed response output.

The two response-bearing records arrived 0.164 seconds apart.

Together, they matched normalized response reference offsets `2:179`:

- Covered bytes: 177 of 179
- Coverage: 98.9%
- Missing range: `0:2`

The two fragments were monotonic and had no internal gap. The second record crossed the sentence boundary and contained the end of the first sentence plus the complete second sentence.

This is strong evidence of fragmented response-text delivery within Rokid binary application messages.

The exact message semantics remain unknown. The records could represent generation chunks, TTS text units, subtitle units, or application state messages.

## ChatGPT-selected response behavior

The ChatGPT-selected capture exposed two transcript-bearing records but no response-bearing records through the tested plaintext response phrases.

This does not prove that response text was absent from every protocol representation. Possible explanations include:

- Different binary encoding.
- Smaller text fragments than the tested phrases.
- Compression.
- Audio-only or media-oriented delivery.
- A message type not decoded by the current phrase scan.

## Comparative conclusion

Both selected models used the same phone-visible Rokid AI WebSocket and showed a similar two-state ASR pattern.

The Gemini-selected capture exposed almost the complete observed response as two ordered plaintext-bearing binary fragments. The ChatGPT-selected capture did not expose its observed response through the tested plaintext phrase matches.

This is an application-protocol difference observed in these controlled captures.

It does not prove that Rokid routed the requests to distinct upstream providers.

## Provider-routing conclusion

The evidence supports:

```text
Hi Rokid
  → Rokid AI gateway
  → upstream provider or model routing not visible from the phone
```

The captures do not prove:

- Direct Google Gemini routing.
- Direct OpenAI ChatGPT routing.
- The identity of the upstream model used for either request.

## Integrity references

Sanitized source-report SHA-256 values:

```text
ChatGPT occurrence-aware report:
0e0b7708b4fc41e56483c0c662067a5c82acca6b139bec6207a23e1d943641f5

Gemini frame-analysis report:
0a2f187d3f97630ef745e5676f93b9aafb576d20982655bd0f9c9c6833c9d871

Gemini response-fragment report:
af2b5c0c69a110a7f1cd1d0fbc127565ababe79dc0a57bdadd8ddf9b706bf42f
```

Raw PCAPs, TLS secrets, decrypted payload indexes, screenshots, logcat output, device identifiers, and private paths are intentionally excluded from this repository.
