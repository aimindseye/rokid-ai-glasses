# AI Assistant Routing

## Finding

Hi Rokid uses a Rokid-managed AI gateway and propagates different opaque
base-model identifiers for ChatGPT and Gemini.

## Endpoint

```text
wss://ai-cloud-global.rokid.com/ws/ai
```

## Route identifiers

| Selection | `base_model_no` |
|---|---|
| ChatGPT | `2d6h8m3qk7s5p9` |
| Gemini | `gEmpl2XKDqHRNDsL` |

The value appeared in `init_scene` and `update_param`.

## Prompt path

The client sent audio frames. The textual question first appeared in server
`recognized_speech`, followed by `llm` and `synthesized_speech`.

## Interpretation

- glasses/app: wake handling, audio capture, session parameters;
- Rokid cloud: ASR, prompt assembly/routing, response streaming;
- downstream provider: hidden behind Rokid's gateway.

## Limits

Not proven:

- exact public model version;
- private system prompt;
- downstream provider request;
- one-to-one route/provider mapping.

Related reports:

- [Test 14A](../tests/14a-ai-assistant-base-model.md)
- [Test 14A-r2](../tests/14a-r2-manual-voice-base-model.md)
