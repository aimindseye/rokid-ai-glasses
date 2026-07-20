# Features and Limitations

## AI assistant

**Observed:** ChatGPT and Gemini selections propagate different opaque route
identifiers.

**Limitation:** the tested phone did not contact public OpenAI or Gemini API
endpoints directly. Exact provider model and system prompt remain hidden.

## Display-free design

Strengths:

- audio-first questions and answers;
- first-person capture;
- voice notes and transcription;
- hands-free calls;
- lightweight form factor.

Limitations:

- no in-lens text;
- no HUD subtitles;
- no visual navigation overlay;
- display-oriented Rokid apps do not automatically transfer to Style.

## Translation

Behavior can vary by mode, language, phone, region, and app version. A prior
tested configuration displayed results on the phone and marked glasses audio
unsupported. That result should not be generalized to every translation mode.

## Local models

Hi Rokid uses a phone compatibility gate. A local Qwen3-family
`Wend_Audio` component was observed, but the tested assistant response path was
cloud-mediated.

## Firmware

The update page requires connected glasses. OTA resolution uses a hybrid
server/client policy; one returned version string alone did not explain the
displayed “latest” status.

## Development

Most public Rokid examples target display-equipped products. Style
compatibility must be demonstrated separately.
