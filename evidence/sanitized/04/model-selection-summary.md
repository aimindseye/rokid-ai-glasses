# Tests 04a and 04b — Sanitized Model-Selection Summary

No raw packet data, TLS secrets, payload bytes, logcat, screenshots, device
identifiers, account identifiers, or private absolute paths are included.

| Property | 04a | 04b |
|---|---|---|
| Transition | ChatGPT to Gemini | Gemini to ChatGPT |
| Vision model | Gemini throughout | Gemini throughout |
| Prompt submitted | No | No |
| Image submitted | No | No |
| Marker result | Valid with documented correction | Valid |
| HTTP request during selection | None identified | None identified |
| Extra WebSocket message | None identified | None identified |
| WebSocket reconnect | None identified | None identified |
| Constant persistent selection field | None identified | None identified |
| Relevant model-selection log event | None identified | None identified |

## 04a persistence summary

- Selection-window traffic matched the periodic binary-message family
- Persistent differences at positions 29 and 41 carried variable values
- Position 44 changed intermittently
- No position retained one constant new post-selection value
- Confidence was limited for the same-length subgroup baseline

## 04b persistence summary

| Direction | Length | Baseline frames | Selection frames | Post-selection frames | Changed stable positions |
|---|---:|---:|---:|---:|---:|
| Client to server | 54 | 5 | 2 | 8 | 0 |
| Server to client | 109 | 5 | 2 | 8 | 0 |

The 04b regular client heartbeat interval had a median of approximately
10.005 seconds and an observed range of 10.000 through 10.007 seconds.

## Cautious conclusion

The selected base model is plausibly stored locally or applied later when
an assistant session begins. The tests do not prove the storage mechanism
and do not attribute a later request to an upstream provider.
