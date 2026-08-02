# Rokid AI Glasses Style — Community Wiki

<!-- wiki-status: audience=all; applies_to=rokid-ai-glasses-style-non-display; evidence=mixed; last_reviewed=2026-07-30 -->

![Product](https://img.shields.io/badge/Product-Rokid%20AI%20Glasses%20Style-111827)
![Form factor](https://img.shields.io/badge/Form%20factor-Display--free-0284c7)
![Guide](https://img.shields.io/badge/Guide-Consumer%20%7C%20Developer%20%7C%20Research-7c3aed)
![Evidence](https://img.shields.io/badge/Evidence-Labeled%20and%20sanitized-16a34a)

An independent, community-maintained wiki for the **display-free Rokid AI
Glasses Style**. Choose the path that matches what you are trying to do.

> Unofficial community project. Not affiliated with Rokid.

## Choose your path

| I am here to… | Start here |
|---|---|
| Set up, use, understand, or troubleshoot the glasses | **[Consumer guide](docs/consumer/README.md)** |
| Build a companion app, on-glasses software, firmware research, or a common smart-glasses platform | **[Developer guide](docs/developer/README.md)** |
| Review validated tests, protocol work, methods, limitations, and sanitized evidence | **[Research library](docs/research/README.md)** |

## Product scope

This repository focuses on **Rokid AI Glasses Style**, the non-display,
audio-first consumer model. It does not assume compatibility with the
separately marketed display-equipped Rokid Glasses or older enterprise devices.
See [Identify your model](docs/consumer/identify-your-model.md) before applying
instructions or community projects.

## What the project currently knows

- The tested unit is a production Android 12/API 32 device with privileged
  Rokid services.
- Hi Rokid is the observed phone-side hub for pairing, configuration, AI,
  visual uploads, media state, and firmware checks.
- The phone was the observed public-network gateway during the qualified voice
  and visual workflows.
- USB ADB was available through the original data/debug cable while Developer
  Mode was enabled; this is not evidence that flashing is safe.
- An independent Android client has completed a qualified RFCOMM connection-only
  lifecycle with zero application bytes.
- Stock Developer Mode actions have been observed and decoded for a bounded
  four-message family; independent command transmission remains prohibited and
  unimplemented.
- A complete replacement companion app, Style-qualified CXR integration, and
  * Test 21 closes the static CXR-L Binder boundary for the accepted `client-l:1.0.1` artifact: all 7 callback interfaces and 21 callback methods have final Stub ↔ Proxy agreement with 0 transaction mismatches; runtime authorization/session semantics remain outside the claim.
  custom firmware have not yet been delivered.

The concise capability boundary is maintained in
[Developer current status](docs/developer/current-status.md). Detailed proof and
release history remain in the [Research library](docs/research/README.md).

## Documentation map

- [Full documentation index](docs/README.md)
- [Shared reference](docs/reference/README.md)
- [Contribution guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Architecture summary](ARCHITECTURE.md)
  * [Test 21 static Binder boundary](docs/research/cxr/test21-static-binder-boundary-overview.md)

## Safety and privacy

Do not publish raw PCAPs, TLS keys, bugreports, HCI logs, APKs, native libraries,
account identifiers, device serials, Bluetooth addresses, tokens, or precise
location. The repository contains sanitized summaries, hashes, and reproducible
public tooling only.
