# AI Models and Assistant Behavior

<!-- wiki-status: audience=consumer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Consumer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Model selection

Hi Rokid offered ChatGPT and Gemini as base-model choices in the tested app.
Changing the selection produced different opaque route identifiers inside the
Rokid-managed AI session.

## What the labels do not prove

The UI label does not independently prove the exact downstream provider model,
model version, system prompt, or routing policy. The tested phone did not expose
a simple direct request to public OpenAI or Gemini API endpoints.

## Voice and visual routes

The app maintained separate identifiers for base-language and visual/multimodal
routes. A visual question can cause the glasses to capture a new image and the
phone to upload it before the answer is generated.

## Local-model option

Hi Rokid exposed a phone-gated local-model workflow and a Qwen3-family
`Wend_Audio` component was observed. The project has not proven that ordinary
assistant responses are fully local or that media remains only on the phone.

## Practical guidance

- Recheck the selected model after app updates or account changes.
- Do not assume privacy behavior from the model name alone.
- Use non-sensitive prompts when comparing models.
- Treat a “local” label as a testable claim, not a guarantee.

## Technical evidence

- [Model-selection finding](../findings/model-selection-behavior.md)
- [AI routing finding](../findings/ai-assistant-routing.md)
- [Controlled model-selection experiment](../experiments/05-gemini-r2-vs-chatgpt-r4.md)
