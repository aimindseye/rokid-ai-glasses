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


## Visual assistant

**Observed:** a visually grounded spoken question does not cause the phone
camera to be used. Rokid's server returns a `take_photo` action, Hi Rokid sends
a camera command to the glasses, and the glasses return a WebP frame over
Bluetooth.

Hi Rokid uploads the frame to Rokid-managed object storage and sends an object
URL to the AI service. Captured images appear as thumbnails beside the
questions in Assistant conversation history.

ChatGPT and Gemini visual selections use different opaque `vl_model_no` values.
The exact downstream provider/model remains hidden.

**Follow-up behavior:** a specific question about a visible detail triggers a
new current-scene capture and a new thumbnail. It does not reuse the prior image
in the tested workflow. A vague reference to “the image you just saw” produced
a clarification question without a new capture.

**Retention:** conversation text and thumbnails survived a Hi Rokid process
restart and remained visible while the phone was offline. The thumbnails were
not normal Android Gallery/MediaStore items; evidence supports a persistent
app-private cache plus a remote cloud object.

**Privacy:** the WebP frames contained no EXIF or GPS metadata, but the broader
AI session carried sensitive account, device, location, and authorization
context.

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


## Background operation

Hi Rokid can continue running after its visible task is removed from Android
Recents. In the tested paired state, the app process, `AiService`,
`LocationService`, glasses connection, and an authenticated AI WebSocket
survived with the screen on and off.

A visible “AI Service” notification is not guaranteed. On the Pixel, Android
notification permission was not granted, yet the services and WebSocket were
active. On the S25, the foreground-service notification was visible when
notifications were allowed.

Android force-stop is stronger than a Recents swipe. It terminated the tested
Hi Rokid runtime and prevented automatic restart until the application was
launched again.

The in-app background-enable banner should not be treated as a reliable status
indicator. On the Pixel, the service was already active before the banner was
satisfied, and selecting Unrestricted battery mode did not change the measured
short-window background behavior.

## First-run and paired data sharing

A clean first launch contacted Rokid and Google/Firebase before Rokid login.
Observed activity included Firebase installation registration, Crashlytics
configuration/logging, app/device metadata, and a Rokid login-token bootstrap
request with an empty `rokidToken`.

After pairing, AI session initialization included sensitive context categories
such as account/device state, precise location fields, weather, model routes,
and payment-capability configuration. This is feature/configuration context;
no Google Wallet, Samsung Wallet, card number, balance, or transaction data was
observed.
