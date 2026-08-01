# Test 20 r2 — sanitized CXR-L event summary

- Firmware: `1.23.009-20260725-153201`
- Hi Rokid: `G1.11.11.0727`
- CXR-L: `com.rokid.cxr:client-l:1.0.1`
- Ordered AI-assist cycles: `2`
- Terminal: `AI_ASSIST_TWO_ORDERED_CYCLES_OBSERVED`
- Clean disconnect: `true`
- Hi Rokid recovery: `true`

## Safety boundary

- Test-app assistant invocation: `NONE`
- Test-app cloud AI request: `NONE`
- Operator spoken AI query: `NONE`
- Camera access by test app: `NONE`
- Microphone access by test app: `NONE`
- Media stream requested by test app: `NONE`

This test qualifies only the two callback methods and the bounded connection/disconnect lifecycle. It does not prove the absence of unrelated stock background network traffic.
