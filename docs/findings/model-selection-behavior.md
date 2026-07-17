# Base-Model Selection Behavior

## Finding

Bidirectional base-model selection did not produce an identifiable immediate
cloud-side update in the observed evidence.

Test 04a changed the base model from ChatGPT to Gemini. Test 04b changed it
from Gemini to ChatGPT. The vision model remained Gemini, and neither test
submitted a prompt or image.

Across both tests:

- No dedicated HTTP preference request was identified
- No additional or out-of-cadence WebSocket message was identified
- No selection-associated WebSocket reconnect was identified
- No constant persistent WebSocket model-state field was identified
- No relevant model preference, model ID, WebSocket-send, GATT, RFCOMM, or
  Bluetooth-write event was identified in available logcat

Test 04b provided the stronger persistence control: zero previously stable
byte positions changed across two selection-window and eight post-selection
messages in each of the regular 54-byte client and 109-byte server families.

## Interpretation boundary

The evidence does not prove that selection is purely local.

Plausible explanations include:

- local application storage;
- deferred transmission when an assistant session begins;
- selection state carried in a later prompt message;
- transmission through an unobserved channel or encrypted inner payload.

The UI labels do not prove direct routing to OpenAI or Google. The immediate
AI peer observed so far is Rokid-operated infrastructure.

## Provider-attribution requirement

Attribution requires prompt-level evidence such as:

- a request field carrying a provider or model identifier;
- a provider-specific hostname;
- a provider-specific response field;
- repeatable model-dependent behavior that excludes other explanations.

Tests 05a and 05b are designed to examine that boundary.
