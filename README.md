# Rokid AI Glasses Research

Independent technical research into the Rokid AI Glasses and the Hi Rokid
Android application.

## Scope

This repository documents:

- Android application behavior and account/device lifecycle
- Network endpoints, protocol usage, and TLS interception methodology
- Bluetooth pairing, device binding, classic Bluetooth, BLE, and RFCOMM
- ChatGPT and Gemini selection and prompt-routing experiments
- Local-model, translation, audio-routing, and device-compatibility checks
- Optional ring and control-panel pairing behavior
- Privacy and security observations

## Current status

Validated through **Test 10c4** using Hi Rokid
`G1.10.11.0713` (`com.rokid.sprite.global.aiapp`, version code `10100011`).

### Test 03 — TLS interception and protocol baseline

- PCAPdroid TLS interception was validated with a unique Firefox HTTPS
  canary before interpreting application traffic.
- Hi Rokid HTTP/1.1, HTTP/2, JSON, and WebSocket traffic was decrypted.
- Rokid model-catalog and AI WebSocket gateway endpoints were identified.
- Idle behavior and model-menu activity were captured without publishing raw
  secrets or unredacted payloads.

### Test 04 — Base-model selection

- Bidirectional base-model selection was tested:
  ChatGPT to Gemini in 04a and Gemini to ChatGPT in 04b.
- Neither selection produced an identifiable immediate HTTP update,
  additional WebSocket message, WebSocket reconnect, or persistent
  WebSocket model-state field.
- Test 04a is accepted with a documented operator-marker correction.
  Test 04b is accepted without a marker correction.
- The captures establish application behavior around model selection, but
  do not prove how the selected provider is represented or applied on
  Rokid's backend.

### Test 05 — ChatGPT and Gemini prompt-routing comparison

- Controlled voice prompt tests were completed with ChatGPT and Gemini
  selected as the base model.
- Both tested modes used Rokid's AI WebSocket gateway:

  ```text
  ai-cloud-global.rokid.com/ws/ai
  ```

- No direct OpenAI or Google model endpoint was observed in the tested
  captures.
- The evidence supports Rokid-mediated AI gateway routing. It does not prove
  which upstream provider handled an individual request or whether the UI
  labels map one-to-one to distinct backend providers.

### Test 06 — Local capability and optional peripherals

- The local-model workflow was blocked on the tested Motorola phone by an
  application compatibility gate requiring newer Android hardware.
- The Device connection feature explicitly describes Bluetooth rings and
  control panels for interaction with the glasses.
- A controlled discovery run found no compatible peripheral. No peripheral
  was selected or paired.
- Static analysis confirmed
  `NativeCXRBridge::startBTPairing(unsigned int)`, which constructs a nested
  `rokid::Caps` command containing `startBTPairing` and sends it toward the
  `CXRControl` endpoint.
- The receiving glasses-firmware behavior was not inspected, so
  glasses-side scanning remains a bounded inference.

### Test 10 — Translation architecture

- Face-to-Face translation consumed audio from the glasses microphone and
  returned spoken output through Bluetooth A2DP to the glasses.
- Online translation used Microsoft Azure Speech infrastructure in the
  tested configuration, including speech recognition, translation, and
  neural text-to-speech.
- Selecting ChatGPT or Gemini as the assistant base model did not produce a
  detectable change in the translation service path.
- The compatible-phone local package was downloaded from Rokid's CDN and
  installed as `wend` version `v2.7.0`.
- The package contains a streaming VAD, a quantized speech encoder, and a
  Qwen3 text model. No identifiable TTS model was present.
- Local recognition and translation ran on the companion phone without
  usable internet access.
- Local spoken output was supplied by Android's Google speech engine. The
  target-language offline voice had to be installed separately.
- A controlled Local-versus-Online run kept Face to Face, language direction,
  and source audio constant. The principal difference was phone-hosted local
  processing versus Microsoft-hosted online processing.

## Evidence policy

Raw captures and credentials are not stored in this public repository.
Public evidence is limited to sanitized endpoint inventories, protocol
summaries, methodology, hash-only manifests, and reviewed redacted excerpts.

Raw PCAP files, TLS key logs, bugreports, logcat files, tokens, account IDs,
device serials, Bluetooth addresses, screenshots, APKs, model binaries,
native libraries, decompiled application trees, and decrypted payloads
remain outside the Git worktree.

See [Evidence Handling](docs/methodology/evidence-handling.md).

## Documentation

- [Test methodology](docs/methodology/test-methodology.md)
- [Test matrix](docs/tests/test-matrix.md)
- [TLS interception baseline](docs/tests/03-tls-interception.md)
- [Base-model selection tests](docs/tests/04-model-selection.md)
- [ChatGPT and Gemini comparison](docs/experiments/05-gemini-r2-vs-chatgpt-r4.md)
- [Device connection test](docs/tests/06c-device-connection.md)
- [Translation overview](docs/tests/10-translation-overview.md)
- [Face-to-Face input routing](docs/tests/10a-face-to-face-input-routing.md)
- [Online translation services](docs/tests/10b-online-translation-services.md)
- [Local-model download provenance](docs/tests/10c1-local-model-download.md)
- [Local-model package analysis](docs/tests/10c2-local-model-package.md)
- [Offline local execution](docs/tests/10c3-offline-local-execution.md)
- [Local-versus-Online flow](docs/tests/10c4-local-vs-online-flow.md)
- [Translation architecture finding](docs/findings/translation-architecture.md)
- [Local `wend` model finding](docs/findings/local-model-wend.md)
- [Translation network-routing finding](docs/findings/translation-network-routing.md)
- [Translation runbook](docs/runbooks/10-translation.md)
- [Endpoint inventory](docs/findings/endpoint-inventory.md)
- [Security and privacy observations](docs/findings/security-and-privacy-observations.md)

## Repository layout

- `docs/methodology/` — test and evidence-handling procedures
- `docs/tests/` — completed test reports and matrix
- `docs/experiments/` — controlled comparisons and bounded investigations
- `docs/runbooks/` — controlled procedures and execution records
- `docs/findings/` — consolidated technical findings
- `evidence/sanitized/` — reviewed public evidence
- `evidence/manifests/` — hash-only provenance records
- `scripts/` — extraction, sanitization, manifest, and validation tools

## Disclaimer

This project is not affiliated with Rokid.

Testing is performed only on devices and accounts controlled by the
repository owner.
