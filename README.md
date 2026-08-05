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
- Test 21 closes the static CXR-L Binder boundary for the accepted `client-l:1.0.1` artifact: all 7 callback interfaces and 21 callback methods have final Stub ↔ Proxy agreement with 0 transaction mismatches; runtime authorization/session semantics remain outside the claim.
- A complete replacement companion app, independent authorization/session reproduction, and custom firmware have not yet been delivered.

The concise capability boundary is maintained in
[Developer current status](docs/developer/current-status.md). Detailed proof and
release history remain in the [Research library](docs/research/README.md).

<!-- test22-final-publication:start -->
## Test 22 independent Wi-Fi boundary

Test 22 is closed. The glasses have a functional Wi-Fi client stack, but the tested ordinary-app AssistServer Wi-Fi request did not create a usable data plane, and the CXR-M-created `wlan0`/IPv4/route session was torn down when the S25 Ultra that established it was powered off. A phone-free persistent route was therefore not proven, so the planned phone-off direct-socket stage was not executed. See [Test 22](docs/tests/test-22-independent-wifi-and-direct-socket.md).

<!-- test22-final-publication:end -->

## Documentation map

- [Full documentation index](docs/README.md)
- [Shared reference](docs/reference/README.md)
- [Contribution guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Architecture summary](ARCHITECTURE.md)
  * [Test 21 static Binder boundary](docs/research/cxr/test21-static-binder-boundary-overview.md)

<!-- r27.1.0-canonical-tooling -->
## Research tooling and revision lineage

Repository-wide tooling normalization is tracked under **R27**. Use the [canonical research tooling index](docs/research/tooling/README.md) and `scripts/rokid-research` to inventory and resolve historical implementations. Revision-named scripts remain preserved for provenance until an explicit equivalence and retirement gate passes; new device testing is paused during this consolidation. R27.1.12 closes the Tests 19–21/r25 retirement queue with 71 compatibility shims and 38 intentionally preserved independent regression-oracle suites; see [R27.1.12](docs/research/r27.1.12-tool-test-oracle-preservation.md).

## Safety and privacy

Do not publish raw PCAPs, TLS keys, bugreports, HCI logs, APKs, native libraries,
account identifiers, device serials, Bluetooth addresses, tokens, or precise
location. The repository contains sanitized summaries, hashes, and reproducible
public tooling only.

## R27 whole-history consolidation complete

R27.2.8 FINAL closes the repository/tooling consolidation program: 88 historical implementations are canonicalized, independent regression oracles remain preserved, and residual low-similarity families are explicitly retained as distinct historical programs. Run `scripts/rokid-research consolidation status` for the machine-readable closure gate. The repository is ready to proceed to Test 22. See [R27.2.8 FINAL](docs/research/r27.2.8-final-consolidation-closure.md).

<!-- r27.3-final-publication -->
## R27 final publication baseline

R27.3 publishes the accepted whole-history consolidation as the clean GitHub baseline before Test 22. The public tree contains the canonical research harness, compatibility shims, preserved regression-oracle source, sanitized historical research source required by those contracts, and closure documentation; private evidence archives and generated artifacts remain excluded. The machine gate remains `scripts/rokid-research consolidation status`, with `R27_WHOLE_HISTORY_CONSOLIDATION=COMPLETE` and `NEXT_DEVICE_TEST_READY=YES` required before new device testing.

## Next qualification

The next controlled device experiment is [Test 22 — Independent On-Glasses Wi-Fi, Routed IP, and Third-Party Direct Socket Capability](docs/tests/test-22-independent-on-glasses-wifi-direct-socket.md). The harness is ready; no result is claimed before live execution.
