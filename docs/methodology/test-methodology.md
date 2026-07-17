# Test Methodology

## Principles

1. Change one variable per capture.
2. Preserve a no-login and post-login baseline before device interaction.
3. Keep model selection separate from prompt submission.
4. Keep base-model and vision-model changes in separate tests.
5. Record exact timestamps, app version, Android user, capture settings, and
   device state.
6. Preserve raw evidence privately and publish only sanitized derivatives.
7. Treat endpoint purpose and upstream-provider attribution as provisional
   unless directly demonstrated by decrypted payloads or repeatable behavior.

## Test environment

- Android application: Hi Rokid
- Package: `com.rokid.sprite.global.aiapp`
- Validated app version: `G1.10.11.0713`
- Android test profile: secondary user ID 10
- Capture tools: PCAPdroid, PCAPdroid MITM addon, adb logcat, tshark/Wireshark
- Bluetooth evidence: Android HCI snoop through bugreport extraction
- Private evidence root: configured locally through `.env.local`

## Network evidence layers

- PCAPdroid CSV: Android app/package attribution and connection statistics
- PCAP plus SSL keylog: packet-level TLS decryption for successfully
  intercepted connections
- Decrypted tshark exports: HTTP/1.1, HTTP/2, JSON, and WebSocket analysis
- adb logcat: application, Bluetooth, and timeline correlation
- Screenshots: proof of the PCAPdroid in-app decryption state

## TLS validation gate

TLS interception is accepted only after a controlled browser request shows:

- a green decrypted connection,
- the unique HTTPS canary path,
- readable request headers,
- readable response status and body.

Hi Rokid testing begins only after this browser gate passes.

## Evidence labels

- `00`: first launch without login
- `01`: login and cloud initialization
- `02b`: owner unbound old account, changed account, and rebound
- `03a`: Firefox TLS interception validation
- `03b`: Hi Rokid idle and model-management TLS baseline
- `04a` and `04b`: model-selection-only tests
- `05a` and `05b`: text canary tests
- `06a` and `06b`: vision canary tests

## Interpretation rules

A UI model label proves only that a selectable option exists. It does not
prove which upstream provider receives a request. A Rokid gateway hostname
proves only the immediate peer. Provider attribution requires request fields,
response fields, provider-specific hostnames, or repeatable model-dependent
behavior.
