# Test 14A-r2 — AI Assistant Base-Model Selection

## Final disposition

**Primary qualification status: PASS**

Test 14A-r2 met its primary objective: determine whether the Hi Rokid ChatGPT/Gemini selector changes the assistant session sent to Rokid's cloud.

The decrypted evidence confirms that:

- ChatGPT and Gemini selections use different `base_model_no` values.
- The selected identifier persists in both `init_scene` and `update_param`.
- Every run created a fresh conversation ID.
- Both selections use the same Rokid-managed assistant WebSocket endpoint.
- The app sends audio and model/session parameters; the textual question first appears in Rokid server-side `recognized_speech` events.
- P1 and P3 provide valid matched-input comparisons.
- P2 is excluded because the operator spoke **“feed”** instead of **“feels”** during the ChatGPT-selected run. It is not an ASR failure and does not require a rerun for the primary qualification objective.

## Evidence integrity

Recovered private evidence bundle:

`14a-r2-manual-voice-base-model-20260720-094245-private-evidence-recovered-r2.zip`

SHA-256:

`dd9c3aa76430cc30ab514754e0296638c3f8a83b8f6a24e7333dd731212ae546`

Validated evidence:

- 6 PCAP files
- 6 SSL key-log files
- 35 additional sidecar files
- 77 manifest entries verified against `SHA256SUMS-private.txt`
- All six assistant WebSocket sessions decrypted successfully
- No TLS application records failed authentication or decryption
- TLS 1.3 cipher: `TLS_AES_256_GCM_SHA384`

## Assistant endpoint and model-routing evidence

All six runs connected to:

`wss://ai-cloud-global.rokid.com/ws/ai`

| UI selection | Opaque `base_model_no` |
|---|---|
| ChatGPT | `2d6h8m3qk7s5p9` |
| Gemini | `gEmpl2XKDqHRNDsL` |

Both selections used the same visual-language model identifier:

`gEmEcBf6rTsSwdRc`

No assistant request was observed going directly to a public OpenAI or Google Gemini API endpoint. Google-hosted traffic in the captures was ancillary Maps/Firebase traffic rather than the assistant LLM stream.

The opaque Rokid identifiers prove distinct routing configurations were requested. They do not independently reveal the exact downstream public model version or prove how Rokid internally fulfills each route.

## Fresh-session isolation

Each app restart produced a distinct conversation ID.

The client-side `agent.question` field was empty in every observed `init_scene` and `update_param` message. No prior question or conversation-history text was observed in client-to-Rokid WebSocket messages.

This confirms that the six trials were isolated from one another at the conversation-session level.

## Prompt-construction path

The decrypted sequence was:

1. The glasses/app initiate the assistant session.
2. The app sends the selected `base_model_no` and session parameters.
3. The app uploads `processing_audio` frames.
4. No textual P1, P2, or P3 question appears in client-to-Rokid messages.
5. Rokid returns incremental `recognized_speech` events.
6. Rokid sends `sentence_complete`.
7. Rokid streams `llm` response events.
8. Rokid returns `synthesized_speech`.

The spoken wake phrase `Hi Rokid` did not appear in the cloud ASR transcript.

**Best-supported interpretation:** the glasses and/or app handle wake activation and audio capture, while Rokid's cloud performs authoritative speech recognition and most likely assembles and routes the downstream model-facing prompt. The exact private system prompt and provider-side request remain hidden behind Rokid's backend.

## Prompt results

### P1 — accepted matched-input pair

Final recognized text was equivalent across both routes:

> The original price is $80. It is discounted by 25%, then 8% sales tax is added answer with only final dollar amount.

Both answered:

> $64.80

Both responses were correct and complied with the requested output format.

| Route | Final ASR → first text | Final ASR → completed text |
|---|---:|---:|
| ChatGPT-selected | 1.742 s | 2.161 s |
| Gemini-selected | 2.214 s | 2.406 s |

### P2 — excluded operator input mismatch

ChatGPT-selected recognized text:

> Explain why metal spoon feed colder than wooden spoon. Use exactly 3 sentences.

Gemini-selected recognized text:

> Explain why a metal spoon feels colder than a wooden spoon. Use exactly 3 sentences.

The operator confirmed that **“feed”** was spoken during the ChatGPT-selected trial. The transcript therefore reflected the actual spoken input.

Classification:

`EXCLUDED_OPERATOR_INPUT_MISMATCH`

This is not:

- an ASR failure,
- a model failure,
- a routing failure, or
- a reason to repeat P2 for Test 14A-r2's primary functional objective.

Both responses were substantively correct and used exactly three sentences, but P2 is excluded from matched-input latency comparison because the spoken questions differed.

### P3 — accepted matched-input pair

Final recognized text was identical across both routes:

> Name 3 differences between Bluetooth Low Energy and Bluetooth Classic. Use exactly 3 numbered lines.

Both responses:

- used exactly three numbered lines,
- correctly contrasted power consumption,
- correctly contrasted throughput/transfer behavior, and
- supplied a reasonable third distinction concerning connection or setup behavior.

| Route | Final ASR → first text | Final ASR → completed text |
|---|---:|---:|
| ChatGPT-selected | 1.788 s | 3.437 s |
| Gemini-selected | 3.982 s | 4.720 s |

## Exploratory latency observations

Using only the two valid matched-input pairs, P1 and P3:

| Route | Mean first-text latency | Mean completed-text latency |
|---|---:|---:|
| ChatGPT-selected | 1.765 s | 2.799 s |
| Gemini-selected | 3.098 s | 3.563 s |

For these two paired observations, the ChatGPT-selected route was approximately:

- 1.333 seconds faster to first text on average
- 0.764 seconds faster to completed text on average

These values are exploratory only. Two paired samples are sufficient for functional comparison but not for a statistically meaningful performance benchmark.

## Final assertions

| Assertion | Final status |
|---|---|
| `EVIDENCE_COMPLETENESS` | **PASS** |
| `TLS_DECRYPTION` | **PASS** |
| `BASE_MODEL_UI_SELECTION_RECORDED` | **CONFIRMED** |
| `BASE_MODEL_SELECTION_PROPAGATED` | **CONFIRMED** |
| `BASE_MODEL_IDENTIFIER_DIFFERS` | **CONFIRMED** |
| `FRESH_CONVERSATION_PER_RUN` | **CONFIRMED** |
| `SAME_ROKID_ASSISTANT_ENDPOINT` | **CONFIRMED** |
| `CLIENT_SENT_AUDIO_STREAM` | **CONFIRMED** |
| `CLIENT_SENT_TEXTUAL_QUESTION` | **NOT OBSERVED** |
| `ROKID_SERVER_RETURNED_ASR_EVENTS` | **CONFIRMED** |
| `ROKID_SERVER_RETURNED_LLM_EVENTS` | **CONFIRMED** |
| `DIRECT_PUBLIC_PROVIDER_API_CONNECTION` | **NOT OBSERVED** |
| `P1_MATCHED_INPUT_PAIR` | **PASS** |
| `P2_MATCHED_INPUT_PAIR` | **EXCLUDED — OPERATOR INPUT MISMATCH** |
| `P3_MATCHED_INPUT_PAIR` | **PASS** |
| `PRIMARY_BASE_MODEL_SELECTION_OBJECTIVE` | **PASS** |
| `STATISTICAL_LATENCY_BENCHMARK` | **NOT ESTABLISHED** |

## Final conclusion

Test 14A-r2 passed its primary qualification objective. The Hi Rokid app propagated distinct ChatGPT and Gemini base-model identifiers into fresh Rokid assistant sessions. Two prompt pairs had matched recognized input and produced valid responses. P2 was excluded because the operator spoke “feed” instead of “feels”; it was not an ASR or model failure.

No additional P2 rerun is required unless a later test aims to establish a larger controlled latency or response-quality benchmark.
