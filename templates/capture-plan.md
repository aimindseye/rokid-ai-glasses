# Capture Plan

Test ID:

Application version:

Selected base model before capture:

Selected vision model before capture:

Exact spoken request:

Expected number of invocations: 1

Expected number of spoken requests: 1

Capture settings:

Required markers:

- BEGIN
- VOICE_READY
- ACTION_START
- ACTION_COMPLETE
- RESPONSE_START
- RESPONSE_COMPLETE
- END

Post-response idle target:

Abort conditions:

- extra assistant invocation;
- repeated prompt;
- capture restart;
- model selection changed unexpectedly;
- unrelated conversation or notification contamination.
