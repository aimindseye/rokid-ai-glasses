# Test 10 Local-Model Metadata

## Download provenance

- Configuration:
  `https://ota-g.rokidcdn.com/sdk/AI/wend/android.latest.json`
- Package:
  `https://ota-g.rokidcdn.com/sdk/AI/wend/v2.7.0/android.zip`
- Package name: `wend`
- Version: `v2.7.0`
- Sequence: `627`
- Backend: CPU
- Installed total: `1,019,916,502` bytes

## Files and SHA-256

| File | Bytes | SHA-256 |
|---|---:|---|
| `adapter.bin` | 379,952,905 | `618549aa8ba7519d25cf905c446c33577c1be9dfe9963e9ab3114671cb338a51` |
| `llm.gguf` | 639,446,752 | `1f20cb82cc9e050a30fa3887c838b9735f98c1f389fd364c419753f935d2660f` |
| `manifest.json` | 841 | `6b128fdbd596069d3606a9d019cdc82b93603cbcc1314a36c6be7724c1e147b8` |
| `vad/am.mvn` | 8,040 | `6820fef9687708c4fc3fab2530179c8fcea6262daa25514380056cd8f6eb1754` |
| `vad/config.yaml` | 1,215 | `69632613638064df8ee3f98eb5fbe8d7cc356636e81594f31356c0c78f5d1459` |
| `vad/model_quant.onnx` | 506,744 | `5289eb2aa3c9af2d7a4284bcfa7c3ceb81d360814ed4203239b6c5d0569da8a1` |
| `version.txt` | 5 | `9316d051b8e321c7f21bdd1b431e881e6a4b0e0759436b97ff06f9092cea4de6` |

## Bounded model interpretation

- `llm.gguf`: Qwen3, 596,049,920 parameters, 28 blocks, primarily Q8_0
- `adapter.bin`: quantized Whisper Large-v1/v2-class speech encoder or
  compatible Rokid derivative
- `vad/model_quant.onnx`: streaming FSMN VAD
- identifiable TTS/vocoder: none

No model binary is included in the public repository.
