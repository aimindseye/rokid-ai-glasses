# Test Methodology

## Principles

1. Change one variable per capture whenever practical.
2. Preserve a no-login and post-login baseline before device interaction.
3. Keep model selection separate from prompt submission.
4. Record exact timestamps, application version, Android user, capture
   settings, and device state.
5. Preserve raw evidence privately and publish only reviewed sanitized
   derivatives.
6. Treat endpoint purpose and upstream-provider attribution as provisional
   unless directly demonstrated by decrypted payloads, application logs, or
   repeatable behavior.
7. State when a run is an architecture test rather than an accuracy,
   latency, or audio-quality benchmark.
8. Record failed or interrupted runs when they explain a dependency or
   limitation.

## Test environments

The project has used more than one controlled Android device. Each report
identifies the relevant environment.

- Earlier baseline and compatibility work used a Motorola Android phone,
  including a secondary Android user.
- Test 10 local-model work used a compatible Samsung flagship phone under
  the owner Android user.
- A second controlled device or a generated audio file was used as an
  external speech source when microphone routing needed to be isolated.
- The application package is `com.rokid.sprite.global.aiapp`.
- Test 10 was validated with Hi Rokid `G1.10.11.0713`.

Raw serials, Bluetooth addresses, account identifiers, exact locations, and
private filesystem roots are excluded from public reports.

## Network evidence layers

- PCAPdroid CSV: application attribution, hostnames, timing, and connection
  statistics
- PCAP plus SSL keylog: packet-level TLS decryption only for connections that
  tolerate interception
- Decrypted tshark exports: HTTP, JSON, and WebSocket analysis
- Android logcat and application logs: execution-path, audio-route, and
  timing correlation
- Android system state: connectivity, policy routing, Bluetooth, and audio
  routing
- Screenshots: private UI-state evidence, not published by default

## TLS validation gate

TLS interception is accepted only after a controlled browser request shows:

- a decrypted connection,
- the unique HTTPS canary path,
- readable request headers,
- readable response status and body.

An application connection that fails only under interception is not treated
as evidence that the underlying feature is broken. A passive control capture
must be run before drawing conclusions.

## Translation-specific controls

For Test 10:

1. Keep the translation mode constant within a comparison. Face to Face was
   used for the Local-versus-Online comparison.
2. Keep source and target languages constant.
3. Use the same prerecorded or generated source-audio file in both phases.
4. For Local mode, disable Wi-Fi and mobile data while preserving Bluetooth.
5. Force-stop and relaunch Hi Rokid after changing network state to avoid
   reusing an existing cloud session.
6. Verify offline state using multiple signals: settings, routes, reachability,
   connectivity state, and application behavior.
7. For Online mode, verify functional internet access. Do not require the
   main `ip route` table to expose a default route because Android policy
   routing may place it in another table.
8. Install the target-language Android offline TTS voice before treating
   local spoken output as an end-to-end offline test.
9. Use passive network capture when TLS interception changes translation
   behavior.
10. Treat a single phrase as a flow canary, not an accuracy benchmark.

## Evidence labels

- `00`: first launch without login
- `01`: login and cloud initialization
- `02b`: owner-authorized account transfer and rebind
- `03a`: Firefox TLS-interception validation
- `03b`: Hi Rokid idle and model-management TLS baseline
- `04a` and `04b`: model-selection-only tests
- `05a` and `05b`: controlled voice-prompt comparisons
- `06c`: optional peripheral connection and pairing control path
- `10a`: Face-to-Face microphone and playback routing
- `10b`: online translation service routing
- `10c1`: local-model download provenance
- `10c2`: local-model package analysis
- `10c3`: offline local execution and Android TTS dependency
- `10c4`: controlled Local-versus-Online execution flow

Private capture folders used earlier `07b` and `07c` aliases. Public
documentation maps those captures into the repository's pre-existing Test 10
translation slot.

## Interpretation rules

A UI model label proves only that a selectable option exists. It does not
prove which upstream provider receives a request.

A Rokid gateway hostname proves only the immediate peer. Provider
attribution requires request fields, response fields, provider-specific
hostnames, application execution logs, or repeatable model-dependent
behavior.

The tested online translation path may be described as Microsoft Azure
Speech because Microsoft service endpoints and Azure translation/TTS
execution were directly observed. That result does not establish that every
region, application version, language pair, or future release uses the same
provider.

The local `wend` package may be described by its observed manifest, model
metadata, headers, and runtime behavior. An exact upstream checkpoint must
not be claimed when only architecture-compatible dimensions are known.
