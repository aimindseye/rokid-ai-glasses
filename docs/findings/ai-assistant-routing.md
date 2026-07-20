# AI Assistant Routing

## Finding

Hi Rokid uses a Rokid-managed AI gateway and maintains separate route
identifiers for base language models and multi/visual models.

## Endpoint

```text
wss://ai-cloud-global.rokid.com/ws/ai
```

## Model catalog

Hi Rokid requested its current model catalog from:

```text
/manager/v3/api/model/aggregate
```

The response separated two categories.

### Base model routes

| UI selection | `modelNo` |
|---|---|
| ChatGPT | `2d6h8m3qk7s5p9` |
| Gemini | `gEmpl2XKDqHRNDsL` |

### Multi/visual routes

| UI selection | `modelNo` |
|---|---|
| ChatGPT | `5d9h11m6qk10s8p12` |
| Gemini | `gEmEcBf6rTsSwdRc` |

## Voice routing

Test 14A-r2 confirmed that ordinary voice sessions propagate the selected base
route through `base_model_no`.

The client sends audio frames. The textual question first appears in
server-side `recognized_speech`, followed by `llm` and `synthesized_speech`.

## Visual routing

Tests 15A and 15B confirmed that visual selection propagates through
`vl_model_no`.

| Visual UI selection | `base_model_no` | `vl_model_no` |
|---|---|---|
| ChatGPT | `gEmpl2XKDqHRNDsL` | `5d9h11m6qk10s8p12` |
| Gemini | `gEmpl2XKDqHRNDsL` | `gEmEcBf6rTsSwdRc` |

Test 15B captured a live ChatGPT-to-Gemini `vl_model_no` transition within one
conversation. `base_model_no` remained unchanged.

Best-supported distinction:

```text
Voice-only selection → base_model_no
Visual selection     → vl_model_no
```

The visual workflow appears to retain a shared/default base route while using
the selected visual route.

## Provider visibility

No direct public OpenAI or Gemini API request was observed from the phone.
Rokid's gateway brokers the visible request and response stream.

The evidence does not prove:

- the exact public model versions;
- private system prompts;
- the downstream provider request;
- one-to-one mapping between route labels and providers;
- the upstream synthesized-speech provider.

## TTS

Rokid's WebSocket supplies `synthesized_speech`. Hi Rokid streams the received
audio to the glasses over Bluetooth.

Android Google TTS initializes but was not observed synthesizing assistant
answers. Microsoft/Azure TTS was not confirmed.

## Related tests

- [Test 14A](../tests/14a-ai-assistant-base-model.md)
- [Test 14A-r2](../tests/14a-r2-manual-voice-base-model.md)
- [Test 15](../tests/15-visual-ai-architecture-routing-retention.md)
