# Test 14A — Initial AI Assistant Base-Model Selection

## Verdict

**Overall status: PARTIAL PASS — selection propagation confirmed; strict provider comparison requires a controlled rerun.**

The decrypted captures prove that the Hi Rokid app sends a different `base_model_no` after selecting ChatGPT versus Gemini. Both selections use the same Rokid-managed WebSocket endpoint and protocol, so Rokid appears to broker the selected model rather than the phone connecting directly to OpenAI or Google model endpoints.

The evidence does **not** independently map the opaque model IDs to public provider/model names, and it cannot prove that the Rokid backend honors the parameter internally. It does, however, rule out the simpler theory that the app sends the same base-model identifier regardless of the UI choice.

## Source evidence

| Role | File | SHA-256 |
|---|---|---|
| ChatGPT capture | `PCAPdroid_20_Jul_08_17_33.pcap` | `8e89b5e08761b598525df596d30252899ef2e261faf929e21c7f08c73eaa5e81` |
| Gemini capture | `PCAPdroid_20_Jul_08_21_59.pcap` | `ee8555e28f4a0d948ca07aa90e78171fc8588e719f6909bb1486efb443295dff` |
| Evidence bundle | `14a-ai-assistant-base-model-20260720-081557-private-evidence-lite(2).zip` | `0eee0531800d559c89362e0a1c91811ecb04557654fc1818e2707b5c5336aa5f` |

## Confirmed transport behavior

Both runs:

- Connect to `ai-cloud-global.rokid.com`.
- Upgrade `GET /ws/ai` to a WebSocket.
- Use the same Hi Rokid package and the same assistant protocol.
- Send audio and assistant-control messages through Rokid infrastructure.
- Receive server-side `recognized_speech`, `llm`, and `synthesized_speech` events.
- Use the same opaque visual-language model identifier.

No assistant request was observed going directly to an OpenAI or Gemini public API hostname. Google-hosted connections in the captures were ancillary Maps/Firebase traffic, not the assistant LLM stream.

## Base-model parameter evidence

| UI selection/run | `base_model_no` sent in `init_scene` and later `update_param` messages |
|---|---|
| ChatGPT | `2d6h8m3qk7s5p9` |
| Gemini | `gEmpl2XKDqHRNDsL` |

The selected value remained stable throughout each run and differed between runs.

The visual-language model value remained the same in both runs:

`gEmEcBf6rTsSwdRc`

## Prompt validity and responses

### Prompt 1 — invalid comparison

Intended prompt:

> A store reduces an eighty-dollar item by twenty-five percent, then adds eight percent sales tax. What is the final price? Answer with only the dollar amount.

ChatGPT-run ASR split the speech into two turns and dropped the `$80` value:

1. `a store reduces`
2. `Item by 25% then adds 8% sales tax. What is the final price answer with only dollar amount?`

The response was therefore appropriately:

> What was the original price of the item?

Gemini-run ASR retained `$80`, and the response was:

> $64.80

**Conclusion:** This difference is caused by unequal recognized input, not reliable evidence of a model-quality difference.

### Prompt 2 — approximate comparison only

ChatGPT final transcript closely matched the intended prompt.

Gemini final transcript became:

> Then why a metal spoon feels colder than a wooden spoon in in exactly 3 sentences?

Both responses contained exactly three sentences and were substantively correct. Because the recognized wording and conversational context differed, this is not a strict identical-input comparison.

### Prompt 3 — valid head-to-head comparison

Both runs produced the same final recognized prompt:

> Name 3 differences between Bluetooth Low Energy and Bluetooth Classic. Use exactly 3 numbered lines.

Both responses:

- Used exactly three numbered lines.
- Correctly contrasted power use and transfer patterns.
- Differed in wording and the third comparison.

This is the strongest behavioral evidence that two distinct routed configurations generated different valid answers.

## Network response timing

Measured from the final `recognized_speech` message to streamed LLM text. These timings exclude completion of TTS playback.

| Run | Prompt | First text | Complete text | Comparison quality |
|---|---:|---:|---:|---|
| ChatGPT | P1 | 2.544 s | 2.612 s | Invalid input comparison |
| ChatGPT | P2 | 1.969 s | 2.753 s | Approximate |
| ChatGPT | P3 | 1.879 s | 3.322 s | Valid |
| Gemini | P1 | 2.905 s | 2.905 s | Invalid input comparison |
| Gemini | P2 | 3.880 s | 4.193 s | Approximate |
| Gemini | P3 | 4.000 s | 4.527 s | Valid |

For the one valid matched prompt, the ChatGPT-selected route produced first text about 2.12 seconds sooner and completed text about 1.21 seconds sooner. This is only one sample and should not be treated as a benchmark.

## Local model observation

Both app launches loaded the same local GGUF model identified in logs as a Qwen3-family, approximately 596-million-parameter `Wend_Audio` model. Because this local model was identical in both runs while the cloud WebSocket carried `llm` response events and differing base-model IDs, it appears to be an ancillary edge/audio component rather than proof that the selected ChatGPT/Gemini answer was generated locally.

## Revised assertions

| Assertion | Re-evaluated status |
|---|---|
| `BASE_MODEL_UI_SELECTION_RECORDED` | **CONFIRMED** |
| `BASE_MODEL_SELECTION_PROPAGATED_TO_ASSISTANT_SESSION` | **CONFIRMED** |
| `BASE_MODEL_IDENTIFIER_DIFFERS_BY_SELECTION` | **CONFIRMED** |
| `SAME_ASSISTANT_ENDPOINT_USED_FOR_BOTH` | **CONFIRMED** |
| `DIRECT_OPENAI_OR_GEMINI_API_CONNECTION_OBSERVED` | **NO** |
| `BASE_MODEL_SELECTION_IGNORED` | **NOT SUPPORTED; substantially weakened** |
| `BACKEND_EXECUTED_PUBLICLY NAMED CHATGPT/GEMINI MODELS` | **NOT DIRECTLY PROVEN** |
| `BASE_MODEL_BEHAVIORAL_DIFFERENCE_OBSERVED` | **YES, but only P3 is a clean comparison** |
| `STRICT THREE-PROMPT MODEL COMPARISON PASSED` | **NO — rerun required** |

## Recommended rerun

Use a new Test 14A-r2 with:

1. A fresh assistant conversation for every model and preferably every prompt.
2. Exact text injection if the app supports it; otherwise play the same prerecorded audio for both models.
3. Verify the final `recognized_speech` text before accepting each trial.
4. Repeat each prompt at least three times per model.
5. Keep the same network, language, TTS voice, and app version.
6. Capture the SSL key log and raw PCAP for every run.
7. Evaluate first-text latency, complete-text latency, instruction compliance, and output similarity only when the recognized prompt is byte-equivalent.

## Privacy note

The decrypted assistant initialization messages contained private account/session identifiers, device identifiers, and precise location/context data. Those values were intentionally excluded from this report.


## Superseding result

Test 14A-r2 corrected the input-control weaknesses and passed the primary qualification objective. See [Test 14A-r2](14a-r2-manual-voice-base-model.md).
