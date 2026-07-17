# Rokid AI WebSocket Observations

Current controlled captures show the Hi Rokid Android application using a binary WebSocket at:

```text
ai-cloud-global.rokid.com/ws/ai
```

Observed properties include:

- two downstream transcript-bearing records consistent with interim/raw and normalized/final ASR states;
- binary application envelopes containing text-bearing regions;
- differing response-text visibility between the Gemini-selected and ChatGPT-selected captures.

The phone-visible evidence supports communication with the Rokid AI gateway. It does not establish direct communication with Google Gemini or OpenAI ChatGPT, and it does not reveal the upstream provider selected behind the gateway.

See `docs/experiments/05-gemini-r2-vs-chatgpt-r4.md` for the controlled comparison.
