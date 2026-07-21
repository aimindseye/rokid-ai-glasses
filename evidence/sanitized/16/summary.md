# Test 16 Sanitized Evidence Summary

Tests 16A–16D established:

- the reviewed installation added only `com.rokid.sprite.global.aiapp`;
- “Rokid AI Service” is an embedded Hi Rokid service, not another app;
- first launch before login contacted Rokid and Google/Firebase and sent
  app/device metadata;
- the pre-login Rokid bootstrap used an empty `rokidToken`;
- paired AI initialization sent account/device, precise-location, weather,
  model-route, calendar, and payment-capability context categories;
- after a Recents swipe, process/services and the existing AI WebSocket
  survived screen-on and screen-off windows;
- post-swipe idle contained periodic ping/pong keepalives without a fresh
  `init_scene`, audio, image, prompt, user-ID, location, or payment-binding
  message;
- notification visibility was not required for the service to run;
- the Pixel background banner did not reflect actual measured service state;
- S25 force-stop terminated the process, services, RFCOMM, and AI WebSocket.

No raw capture, TLS key, account/device identifier, credential, coordinate,
image, audio, or decrypted value is included here.
