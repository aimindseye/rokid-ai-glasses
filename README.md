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

Validated through **Test 06c** using Hi Rokid
`G1.10.11.0713` (`com.rokid.sprite.global.aiapp`, version code `10100011`).

### Test 03 — TLS interception and protocol baseline

- PCAPdroid TLS interception was validated with a unique Firefox HTTPS
  canary before interpreting application traffic.
- Hi Rokid HTTP/1.1, HTTP/2, JSON, and WebSocket traffic was decrypted.
- Rokid model-catalog and AI WebSocket gateway endpoints were identified.
- Idle behavior and model-menu activity were captured without relying on
  raw secrets or unredacted payloads in the public repository.

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
- The evidence supports Rokid-mediated AI gateway routing. It does not
  prove which upstream provider handled any individual request or whether
  the selected labels map one-to-one to distinct backend providers.

### Test 06 — Local capability, translation, and optional peripherals

- The local/offline model workflow was blocked on the tested Motorola Razr
  by an application compatibility gate requiring a Snapdragon 8 Gen 2 or
  newer Android device.
- In the tested Hi Rokid translation configuration, the application marked
  glasses audio as unsupported and displayed DuoTalking results on the
  phone. This is a configuration-specific result, not a categorical claim
  that custom translation or audio-routing workflows are impossible.
- The Device connection feature explicitly describes Bluetooth rings and
  control panels for interaction with the glasses.
- A controlled discovery run found no compatible peripheral. No peripheral
  was selected or paired.
- No phone-side Rokid-specific BLE filter was identified by device name,
  primary UUID, solicitation UUID, or manufacturer identifier.
- Static analysis confirmed
  `NativeCXRBridge::startBTPairing(unsigned int)`. The function constructs
  a nested `rokid::Caps` command containing `startBTPairing` and sends it
  toward the `CXRControl` endpoint.
- The evidence strongly supports the phone delegating pairing initiation to
  the connected glasses control plane. The receiving glasses-firmware
  behavior was not inspected, so glasses-side BLE scanning remains a
  bounded inference rather than a directly observed implementation detail.
- Ring advertisement data, GATT services, authentication, and input-event
  encoding remain unknown. This workstream is closed because no compatible
  reference peripheral is available and none will be purchased for this
  effort.

## Evidence policy

Raw captures and credentials are not stored in this public repository.
Public evidence is limited to sanitized endpoint inventories, protocol
summaries, methodology, hash-only manifests, and reviewed redacted excerpts.

Raw PCAP files, TLS key logs, bugreports, logcat files, tokens, account IDs,
device serials, Bluetooth addresses, screenshots, APKs, native libraries,
decompiled application trees, and decrypted payloads remain outside the Git
worktree.

See [Evidence Handling](docs/methodology/evidence-handling.md).

## Documentation

- [Test methodology](docs/methodology/test-methodology.md)
- [Test matrix](docs/tests/test-matrix.md)
- [TLS interception baseline](docs/tests/03-tls-interception.md)
- [Base-model selection tests](docs/tests/04-model-selection.md)
- [ChatGPT and Gemini comparison](docs/experiments/05-gemini-r2-vs-chatgpt-r4.md)
- [Device connection test](docs/tests/06c-device-connection.md)
- [Peripheral pairing experiment](docs/experiments/06c-device-connection-peripheral-pairing.md)
- [Peripheral pairing control path](docs/findings/peripheral-pairing-control-path.md)
- [Native CXR static-analysis method](docs/methodology/native-cxr-static-analysis.md)
- [Endpoint inventory](docs/findings/endpoint-inventory.md)
- [Model-selection behavior](docs/findings/model-selection-behavior.md)
- [Security and privacy observations](docs/findings/security-and-privacy-observations.md)
- [Executed model-selection runbook](docs/runbooks/04-model-selection.md)

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
