# Local Model Finding — `wend`

## Identity

- Package name: `wend`
- Version: `v2.7.0`
- Sequence: `627`
- Backend: CPU
- Installed total: `1,019,916,502` bytes
- Supported translation languages declared by the manifest:
  Chinese, English, Japanese, Korean, French, German, and Spanish

## Package composition

```text
wend/
├── adapter.bin
├── llm.gguf
├── manifest.json
├── version.txt
└── vad/
    ├── am.mvn
    ├── config.yaml
    └── model_quant.onnx
```

## Text model

The GGUF text model is a 596,049,920-parameter Qwen3 model with 28 blocks,
40,960 context length, 1,024 embedding width, and primarily Q8_0 weights.

## Speech encoder

The quantized adapter has GGML audio dimensions compatible with a Whisper
Large-v1/v2-class encoder. It uses 80 mel bins, 32 audio layers, 20 attention
heads, and 1,280 audio-state width.

The exact source checkpoint is not proven. "Whisper-derived" or
"Whisper Large-v1/v2-class" is the appropriate bounded description.

## VAD

The package includes a streaming FSMN VAD for 16 kHz audio. Its configuration
uses 25 ms frames, 10 ms shifts, left-context FSMN layers, and bounded start,
end, and segment timers.

## Runtime role

The package supplies the Local speech-understanding pipeline:

```text
voice activity detection
-> speech encoding
-> local transcription
-> local translation
```

## What it does not contain

No identifiable TTS model, vocoder, or language-specific voice resource was
found.

Runtime tests confirmed that Hi Rokid sends Local translated text to
Android's TTS engine. Therefore `wend` is not a self-contained spoken
translation package.
