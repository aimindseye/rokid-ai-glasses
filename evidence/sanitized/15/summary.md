# Test 15 Sanitized Summary

Test 15 combined visual workflow discovery and routing/retention qualification.

Confirmed:

- visual speech is recognized by Rokid before a `take_photo` tool action;
- the glasses return a WebP frame over Bluetooth;
- Hi Rokid uploads the image to Rokid-managed object storage;
- the AI WebSocket receives an object URL, not raw image bytes;
- ChatGPT and Gemini visual selections use different `vl_model_no` routes;
- a live ChatGPT-to-Gemini visual-route switch occurred in one conversation;
- specific visual follow-ups capture a fresh current-scene image;
- prior-image reuse for grounded follow-ups was not observed;
- conversation text and thumbnails survive process restart and work offline;
- thumbnails are stored in a persistent app-private cache;
- synthesized answer audio originates from Rokid's cloud and is streamed to the
  glasses;
- phone TTS and Microsoft TTS were not observed generating the answers.

Raw images, screenshots, captures, TLS keys, HCI logs, complete object URLs,
tokens, account/device/location data, and bugreports remain private.
