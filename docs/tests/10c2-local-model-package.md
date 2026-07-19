# Test 10c2 — Local-Model Package Analysis

## Status

Complete — PASS.

## Question

What is inside the installed `wend` package?

## Observed package manifest

The package manifest describes `wend` `v2.7.0` as a CPU-backed multi-task
model supporting transcription, translation, and chat. The listed
translation languages are Chinese, English, Japanese, Korean, French,
German, and Spanish.

## Installed files

| File | Size in bytes | SHA-256 |
|---|---:|---|
| `adapter.bin` | 379,952,905 | `618549aa8ba7519d25cf905c446c33577c1be9dfe9963e9ab3114671cb338a51` |
| `llm.gguf` | 639,446,752 | `1f20cb82cc9e050a30fa3887c838b9735f98c1f389fd364c419753f935d2660f` |
| `manifest.json` | 841 | `6b128fdbd596069d3606a9d019cdc82b93603cbcc1314a36c6be7724c1e147b8` |
| `vad/am.mvn` | 8,040 | `6820fef9687708c4fc3fab2530179c8fcea6262daa25514380056cd8f6eb1754` |
| `vad/config.yaml` | 1,215 | `69632613638064df8ee3f98eb5fbe8d7cc356636e81594f31356c0c78f5d1459` |
| `vad/model_quant.onnx` | 506,744 | `5289eb2aa3c9af2d7a4284bcfa7c3ceb81d360814ed4203239b6c5d0569da8a1` |
| `version.txt` | 5 | `9316d051b8e321c7f21bdd1b431e881e6a4b0e0759436b97ff06f9092cea4de6` |

## Qwen text model

`llm.gguf` is GGUF version 3 with 310 tensors and architecture `qwen3`.

Observed metadata includes:

| Property | Value |
|---|---:|
| Exact parameter count | 596,049,920 |
| Block count | 28 |
| Context length | 40,960 |
| Embedding width | 1,024 |
| Feed-forward width | 3,072 |
| Attention heads | 16 |
| Key/value heads | 8 |
| Token count | 151,936 |
| Primary quantization | Q8_0 |

Most model parameters are stored as Q8_0, with a small set of F32
normalization tensors.

## Audio adapter

`adapter.bin` begins with legacy GGML magic and reports audio dimensions
compatible with a Whisper Large-v1/v2-class encoder:

- audio context: `1500`
- audio state: `1280`
- attention heads: `20`
- audio layers: `32`
- mel bins: `80`
- package quantization label: `q4_0_4_8`

Tensor names include audio encoder convolution and positional-embedding
components.

This supports describing the file as a quantized Whisper Large-v1/v2-class
speech encoder or Rokid derivative. It does not identify an exact upstream
checkpoint.

Assuming the standard compatible encoder topology, the speech encoder is
approximately 636.8 million parameters. That makes the combined speech and
text stack approximately 1.23 billion parameters, with the audio-side count
remaining an architectural estimate.

## VAD

The ONNX component is a streaming FSMN voice-activity detector configured
for:

- 16 kHz audio,
- 80 mel features,
- 25 ms frames,
- 10 ms frame shift,
- four FSMN layers,
- left context only,
- 3 seconds maximum start silence,
- 800 ms maximum end silence, and
- 10 seconds maximum segment length.

## TTS finding

No identifiable TTS model, vocoder, or target-language voice asset was found
inside `wend`.

The later execution tests confirmed that Local spoken output is delegated to
Android's installed TTS engine rather than synthesized by this package.
