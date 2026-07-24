# Rokid AI Glasses Style — Consumer, Developer, and Research Guide

![Product](https://img.shields.io/badge/Product-Rokid%20AI%20Glasses%20Style-111827)
![Form factor](https://img.shields.io/badge/Form%20factor-Display--free-0284c7)
![Audience](https://img.shields.io/badge/Audience-Consumers%20%7C%20Developers%20%7C%20Researchers-7c3aed)
![Evidence](https://img.shields.io/badge/Evidence-Sanitized%20and%20reproducible-16a34a)

An independent, community-maintained guide to the **display-free Rokid AI
Glasses Style** and the **Hi Rokid** companion app.

This repository is designed as a one-stop starting point for:

- consumers deciding whether the glasses fit their needs;
- owners setting up, updating, and troubleshooting the product;
- developers evaluating SDKs, companion applications, and community projects;
- researchers studying Bluetooth, cloud AI, visual AI, local models, privacy, and firmware.

> Unofficial community project. Not affiliated with Rokid.

---

## Headline finding

> **The tested US non-display Rokid AI Glasses are a full Android 12 device. The retail production build exposes RSA-protected USB ADB when Developer Mode is enabled, contains a privileged on-glasses Rokid application stack, and runs a root TEE-domain daemon listening on TCP port 8341. During tested voice and visual AI workflows, the glasses did not activate Wi-Fi, Wi-Fi Direct or an IP route; the paired phone remained the cloud-network gateway.**

---

## Contents

- [Headline finding](#headline-finding)
- [Start here](#start-here)
- [What this product is](#what-this-product-is)
- [Quick answers](#quick-answers)
- [Consumer guide](#consumer-guide)
- [Phone and local-model compatibility](#phone-and-local-model-compatibility)
- [Architecture](#architecture)
- [Developer resources](#developer-resources)
- [Validated research](#validated-research)
- [Privacy and evidence](#privacy-and-evidence)
- [Repository layout](#repository-layout)
- [Contributing](#contributing)

## Start here

| Goal | Recommended page |
|---|---|
| Understand the product | [Product overview](docs/consumer/product-overview.md) |
| Pair and configure the glasses | [Getting started](docs/consumer/getting-started.md) |
| Check phone or local-model support | [Phone compatibility](docs/consumer/phone-and-local-model-compatibility.md) |
| Troubleshoot pairing, power, or updates | [Troubleshooting](docs/consumer/troubleshooting.md) |
| Understand the non-display architecture | [Architecture](docs/architecture/non-display-system-architecture.md) |
| Evaluate SDK and development options | [SDK guide](docs/development/sdk-and-development-options.md) |
| Find community projects | [Community ecosystem](docs/development/community-ecosystem.md) |
| Review independent tests | [Test matrix](docs/tests/test-matrix.md) |
| Understand the visual-assistant workflow | [Visual AI workflow](docs/findings/visual-ai-workflow.md) |
| Understand Android background services and data sharing | [Background services finding](docs/findings/background-services-and-data-sharing.md) |
| Understand the glasses OS, USB ADB, and local services | [Glasses OS & Services](docs/tests/17-glasses-os-adb-and-network-exposure.md) |
| Understand ADB control, stale-state risk, and cable uncertainty | [Test 18](docs/tests/18-usb-adb-control-and-cable-analysis.md) |
| Reproduce a test | [Public scripts](scripts/README.md) |

## What this product is

This repository focuses on **Rokid AI Glasses Style**, the display-free,
voice-first model. Some packaging and app screens may use the shorter name
“Rokid AI Glasses.” It should not be confused with **Rokid Glasses**, the
separate display-equipped product.

The Style experience centers on:

- a first-person camera;
- microphones and open-ear speakers;
- voice-first AI interaction;
- Bluetooth and Wi-Fi connectivity;
- the Hi Rokid phone application;
- audio and phone-screen output instead of an in-lens HUD.

See [Product overview](docs/consumer/product-overview.md).

## Quick answers

### Does the Style model have a display?

No. It is display-free. Responses and status are delivered mainly through
open-ear audio and Hi Rokid on the phone.

### Is a phone required?

Some capture and audio functions may work without continuous phone interaction,
but Hi Rokid is central to pairing, settings, AI model selection, local-model
management, media, translation configuration, and firmware updates.

### Does selecting ChatGPT or Gemini change anything?

Yes. Test 14A-r2 confirmed that Hi Rokid sends different opaque
`base_model_no` values for the ChatGPT and Gemini selections. Both use a
Rokid-managed AI WebSocket gateway. The evidence does not expose the exact
downstream public model version.

### Are assistant answers generated locally?

The tested assistant path was cloud-mediated: the app uploaded audio and
received server-side speech recognition, LLM text, and synthesized speech. A
local Qwen3-family `Wend_Audio` component was observed, but it was identical
across both routes and is not proof of local answer generation.


### How does the visual assistant handle an image?

A visually grounded question is recognized by Rokid's cloud, which returns a
`take_photo` tool action. Hi Rokid then asks the glasses to capture a WebP
frame, receives it over Bluetooth, uploads it to Rokid-managed object storage,
and sends the object URL through the AI WebSocket.

ChatGPT and Gemini visual selections use different `vl_model_no` routes.
Specific visual follow-ups take a **new current-scene photo** rather than
reusing the previous frame. Conversation thumbnails remain available from a
local app-private cache after a process restart and while the phone is offline.

See [Test 15](docs/tests/15-visual-ai-architecture-routing-retention.md).

### What happens after Hi Rokid is swiped away?

Removing Hi Rokid from Android Recents removes the visible task, but it does
not necessarily stop the companion runtime. Tests 16A and 16D observed the Hi
Rokid process, `AiService`, `LocationService`, the glasses connection, and the
Rokid AI WebSocket continuing with periodic ping/pong traffic while the screen
was on and off.

Android **force-stop** is a different boundary. The S25 control terminated the
Hi Rokid process, foreground services, Bluetooth RFCOMM connection, and AI
WebSocket and prevented automatic restart until the app was launched again.

On the Pixel, the service ran even though the app's notification permission was
not granted, so no visible “AI Service” notification appeared. Notification
visibility is not a reliable proxy for service activity.

See [Test 16](docs/tests/16-android-background-services-package-lineage-data-sharing.md).

### Do the non-display glasses run Android and support USB ADB?

Yes on the tested US unit. Test 17 identified Android 12/API 32 on a production
`user/release-keys` build and confirmed RSA-protected USB ADB through the
original Rokid data/debug cable. Wireless ADB was disabled.

The same unit reported `verifiedbootstate=orange` and
`vbmeta.device_state=unlocked`; the origin was not determined, and no flashing,
root, relocking, or partition modification was attempted.

During tested stock voice and visual-AI requests, the glasses did not activate
Wi-Fi, Wi-Fi Direct, Wi-Fi Aware, or an IP route. The paired phone remained the
strongly supported cloud-network gateway.

See [Test 17](docs/tests/17-glasses-os-adb-and-network-exposure.md).

### How are firmware updates checked?

When the glasses are connected, Hi Rokid checks automatically after app launch,
checks again when the firmware page opens, and sends a new live request for
each manual check. The app submits the installed version to Rokid's OTA service
and receives a complete OTA manifest.

### Which phones support local models?

Hi Rokid contains an in-app “tested and available” list. The captured list and
its limitations are documented in
[Phone and local-model compatibility](docs/consumer/phone-and-local-model-compatibility.md).

## Consumer guide

- [Product overview](docs/consumer/product-overview.md)
- [Getting started](docs/consumer/getting-started.md)
- [Features and limitations](docs/consumer/features-and-limitations.md)
- [Phone and local-model compatibility](docs/consumer/phone-and-local-model-compatibility.md)
- [Troubleshooting](docs/consumer/troubleshooting.md)

## Phone and local-model compatibility

The current development lab uses a **Pixel 7** as the dedicated Rokid test and
development phone. A **Samsung Galaxy S25 Ultra** remains the regular phone and
was used for earlier lifecycle comparison. Migration of the glasses back to the
S25 is intentionally deferred until custom applications work on the Pixel.

Hi Rokid's in-app **tested-and-available** list for local models, captured on
2026-07-20, enumerated these devices:

- **Xiaomi:** 15 Ultra; 17; 17 Max; 17 Pro Max
- **Redmi:** K80 Pro; K90; K90 Pro Max
- **OPPO:** Find N5; Find N6 Collector Edition; Find X7 Ultra; Find X8 Ultra;
  Find X9 Ultra
- **realme:** Neo8
- **OnePlus:** 12; Ace 3 Pro; Ace 6T; 15R
- **vivo:** X300 Ultra; X300 FE; S50 Pro Mini
- **iQOO:** 13
- **Samsung:** Galaxy S25 Ultra; Galaxy S26; Galaxy S26+; Galaxy S26 Ultra
- **Apple:** iPhone 17 Pro
- **Sony:** Xperia 1 VII

This is an app-version snapshot, not a permanent support guarantee. The names
above are transcribed from the Hi Rokid screen and may be region-specific.

## Architecture

The [architecture guide](docs/architecture/non-display-system-architecture.md)
separates:

1. glasses hardware and embedded software;
2. Bluetooth/Wi-Fi device and media channels;
3. the Hi Rokid phone application;
4. Rokid-operated AI, OTA, account, mapping, and ancillary services.

Validated flows:

- [AI assistant routing](docs/findings/ai-assistant-routing.md)
- [Visual AI workflow](docs/findings/visual-ai-workflow.md)
- [Background services and data sharing](docs/findings/background-services-and-data-sharing.md)
- [Glasses Android OS and USB ADB](docs/findings/glasses-android-os-and-adb.md)
- [Glasses local services and TCP port 8341](docs/findings/glasses-local-services-and-port-8341.md)
- [Firmware update path](docs/findings/firmware-update-path.md)

## Developer resources

Rokid development material spans several product families. Do not assume a
sample built for display-equipped Rokid Glasses will work on the display-free
Style model.

Start with:

- [SDK and development options](docs/development/sdk-and-development-options.md)
- [Community ecosystem](docs/development/community-ecosystem.md)
- [Non-display architecture](docs/architecture/non-display-system-architecture.md)
- [awesome-rokid](https://github.com/Anezium/awesome-rokid), a broader index
  across many Rokid products
- [Community Rokid platform documentation](https://github.com/buildwithfenna/rokid-docs)

SDK and project references are included for discovery even where Style
compatibility has not yet been validated.

## Validated research

Published qualification sets include:

- **Test 14A / 14A-r2** — voice assistant ChatGPT/Gemini routing;
- **Test 14B** — firmware-check triggers and OTA version resolution;
- **Test 15A / 15B** — visual capture, routing, retention, and context behavior;
- **Test 16A–16D** — Android package lineage, first-run telemetry, pairing-time
  context, background-service persistence, force-stop behavior, and Pixel/S25
  comparison;
- **Test 17A–17F** — glasses Android/boot/USB-ADB baseline, privileged local
* Test 18A–18D — offline ADB-toggle control-path analysis, privilege/domain boundaries, cable/debug-board evidence, and recovery safety assessment.
  services, package hashes, port 8341, and passive voice/visual interface tests.

Highlights:

- Voice ChatGPT and Gemini selections propagate different `base_model_no`
  values.
- Visual ChatGPT and Gemini selections propagate different `vl_model_no`
  values while the visual base route remains fixed.
- Assistant audio is sent to a Rokid-managed WebSocket gateway.
- Text first appears in server-side `recognized_speech`.
- Visual questions trigger a server `take_photo` tool action.
- The glasses return WebP images over Bluetooth; Hi Rokid uploads them to
  Rokid-managed Aliyun OSS and sends object URLs to the AI service.
- Specific visual follow-ups recapture the current scene rather than reusing
  the previous image.
- Conversation text and thumbnails remain available offline from a persistent
  app-private cache.
- AI answer speech is synthesized in Rokid's cloud and streamed to the glasses;
  phone TTS was not observed generating those answers.
- No direct public OpenAI, Gemini, Microsoft TTS, or other downstream provider
  API request was observed from the phone.
- Firmware checking is connection-gated and uses a hybrid server/client policy.
- A clean Pixel install added only `com.rokid.sprite.global.aiapp`; no separate
  “Rokid AI Service,” Baidu, or delayed companion package was installed.
- Before Rokid login, Hi Rokid registered a Firebase installation, sent
  app/device telemetry, and called Rokid's token bootstrap with an empty
  `rokidToken`.
- Pairing and AI connection initialization sent an `init_scene` context that
  included account/device state, precise location fields, weather, model
  routes, and payment-capability configuration.
- After a Recents swipe, the existing WebSocket remained open with roughly
  ten-second ping/pong keepalives; fresh audio, image, prompt, or context
  resends were not observed during the tested idle windows.
- The in-app “run in background” banner did not accurately describe actual
  service state on the Pixel; the service was already active before selecting
  Android Unrestricted battery mode.
- The tested glasses are an Android 12 production device with RSA-protected USB
  ADB persistently configured and wireless ADB disabled.
- Boot properties reported orange/unlocked state; no bootloader or flashing
  experiment was performed.
- A privileged on-glasses Rokid service stack and a root TEE-domain listener on
  TCP 8341 were observed. No request was sent to that listener.
- Neither the tested stock voice nor fresh-image visual workflow activated a
  glasses Wi-Fi/P2P interface or IPv4 route.

See [Test matrix](docs/tests/test-matrix.md).

## Privacy and evidence

Raw captures and credentials are not stored in this public repository.

Do not commit:

- PCAP/PCAPNG files or TLS key logs;
- raw logcat, bugreports, HCI logs, or decrypted payload dumps;
- tokens, account IDs, serials, Bluetooth addresses, or precise location;
- APKs, native libraries, or decompiled application trees;
- ADB host keys, device authorization files, or USB/device serials;
- complete block-device maps or boot/vbmeta/vendor/partition images;
- screenshots containing private account or device information.

Public material is limited to sanitized reports, generalized scripts,
non-sensitive images, protocol summaries, and hash-only provenance records.

See [Evidence handling](docs/methodology/evidence-handling.md).

## Repository layout

- `docs/consumer/` — ownership, setup, compatibility, features, troubleshooting
- `docs/architecture/` — non-display hardware/app/cloud architecture
- `docs/development/` — SDK applicability and community projects
- `docs/tests/` — completed reports and master matrix
- `docs/runbooks/` — reproducible procedures
- `docs/findings/` — consolidated findings
- `docs/methodology/` — evidence and analysis procedures
- `docs/research/` — evidence levels and interpretation rules
- `docs/assets/` — reviewed public images
- `evidence/sanitized/` — public summaries derived from private captures
- `evidence/manifests/` — hash-only provenance
- `scripts/tests/` — interactive capture runners
- `scripts/recovery/` — bounded MediaStore recovery/finalization
- `scripts/safety/` — public-repository privacy gates

## Contributing

Contributions are welcome for consumer guidance, compatibility reports,
developer resources, reproducible tests, and corrections.

Label important claims as:

- **Official** — stated by Rokid;
- **Observed** — captured or reproduced;
- **Inferred** — best-supported interpretation;
- **Unverified** — listed for discovery but not tested.

Read [CONTRIBUTING.md](CONTRIBUTING.md).

## Disclaimer

This project is not affiliated with Rokid. Product names and trademarks belong
to their respective owners. Testing is performed only on devices and accounts
controlled by the repository owner.

## Test 18 highlight

* Static OTA analysis identified `settings_developer_mode`, a vendor ADB property path, and a possible disable-path stale-state asymmetry; runtime state and cable cause remain unresolved.
