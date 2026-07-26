# Rokid AI Glasses Style — Consumer, Developer, and Research Guide

![Product](https://img.shields.io/badge/Product-Rokid%20AI%20Glasses%20Style-111827)
![Form factor](https://img.shields.io/badge/Form%20factor-Display--free-0284c7)
![Coverage](https://img.shields.io/badge/Coverage-Tests%2000%E2%80%9318%20%7C%20Research%20through%20r24.1-7c3aed)
![Evidence](https://img.shields.io/badge/Evidence-Sanitized%20and%20reproducible-16a34a)

An independent, community-maintained guide to the **display-free Rokid AI
Glasses Style**, the **Hi Rokid** Android companion application, and the
validated research completed through **Test 18** and **research release
r1.3.3.2.24.1**.

> Unofficial community project. Not affiliated with Rokid.

## Current state in one page

The project has established three complementary layers:

1. **Glasses and stock workflow behavior.** The tested US non-display glasses
   run Android 12, expose RSA-protected USB ADB when Developer Mode is enabled,
   contain a privileged Rokid service stack, and keep a root TEE-domain service
   listening on TCP 8341. During the tested voice and visual workflows, the
   glasses did not establish a Wi-Fi, Wi-Fi Direct, Wi-Fi Aware, or routed IP
   session; the paired phone remained the observed cloud gateway.
2. **Hi Rokid cloud and lifecycle behavior.** The companion app handles account
   binding, Bluetooth media/control transport, AI WebSocket sessions, visual
   uploads, firmware checks, model routing, background services, and local
   conversation retention. Tests 14–18 document these boundaries.
3. **Protected companion startup.** The native-loader research recovered the
   wrapper/native handoff, exact `MyJni` registration map, startup
   materialization, zero-hook injection trigger boundary, and an APK-enhanced
   caller census. It did not recover the complete protected application or an
   independent phone-to-glasses protocol implementation.

### Replacement-app readiness

| Capability | Current status | Best current reference |
|---|---|---|
| Stock pairing and cloud workflow observation | Substantially complete | [Test matrix](docs/tests/test-matrix.md) |
| Glasses Android/ADB/local-service baseline | Complete in read-only scope | [Test 17](docs/tests/17-glasses-os-adb-and-network-exposure.md) |
| Developer Mode property semantics | Complete statically | [USB ADB finding](docs/findings/glasses-android-os-and-adb.md#usb-adb-control-path-follow-up) |
| Phone-to-glasses command/session framing | Partial | [Project status](docs/project-status.md) |
| Remote Developer Mode invocation | Unresolved | [Architecture](docs/architecture/non-display-system-architecture.md#replacement-companion-readiness) |
| Independent Android companion client | Not implemented | [Project status](docs/project-status.md) |

The immediate engineering gap is therefore **not broad transport discovery**.
It is exact stock pairing/session closure, command/reply attribution, and a
minimal independent Android client that first reproduces a harmless read-only
operation before any guarded Developer Mode toggle.

## Start here

| Goal | Page |
|---|---|
| Understand what is proven and what remains | [Project status](docs/project-status.md) |
| Understand the product | [Product overview](docs/consumer/product-overview.md) |
| Set up or troubleshoot the glasses | [Consumer documentation](docs/consumer/README.md) |
| Understand the full system | [Architecture overview](ARCHITECTURE.md) |
| Review all numbered tests and research releases | [Test and research matrix](docs/tests/test-matrix.md) |
| Review stock app/device findings | [Findings index](docs/findings/README.md) |
| Review protected native-loader research | [Native-loader research](docs/research/native-loader/README.md) |
| Review r24.1 APK-enhanced caller analysis | [Protected-application research](docs/research/protected-application/README.md) |
| Run available public procedures | [Runbooks](docs/runbooks/README.md) |
| Find public scripts | [Scripts index](scripts/README.md) |
| Understand public/private evidence boundaries | [Evidence index](evidence/README.md) |

## Key validated findings

### Product and on-glasses system

- The target is the **display-free** Rokid AI Glasses Style, not the separate
  display-equipped Rokid Glasses product.
- The tested unit reports Android 12/API 32 on an arm64 production
  `user/release-keys` build.
- USB ADB uses Android RSA authorization; wireless/TCP ADB was disabled in the
  captured state.
- Boot properties reported orange/unlocked state. This project did not unlock,
  root, flash, relock, or modify partitions.
- The on-glasses service stack includes assistant, system control, media, TTS,
  Bluetooth, Wi-Fi, payment, OTA, camera, and screen-stream components.
- `GateServiced` is the very-high-confidence owner of a root/TEE-domain listener
  on TCP 8341. No request was sent to that listener.

### Phone, AI, visual, and OTA workflows

- ChatGPT and Gemini selections propagate different opaque `base_model_no`
  values through a Rokid-managed AI WebSocket.
- Visual routes use different `vl_model_no` values.
- Voice text first appears in server-side `recognized_speech`; the phone did
  not directly call a public OpenAI or Gemini API in the captured paths.
- Visual requests trigger a server `take_photo` action. A WebP frame returns
  from the glasses over Bluetooth, is uploaded by Hi Rokid to Rokid-managed
  object storage, and is referenced in the AI session.
- Specific visual follow-ups capture a new current-scene image.
- Conversation text and thumbnails persisted in the app-private cache across
  restart and offline review in the tested scope.
- Removing Hi Rokid from Recents did not necessarily stop `AiService`, the
  glasses connection, or WebSocket keepalives. Android force-stop did.
- Firmware checks are connection-gated and produce fresh live OTA requests on
  cold launch, firmware-page entry, and manual checks.

### Developer Mode and USB ADB control path

Static analysis recovered the glasses-side setting key and property writes:

```text
settings_developer_mode = on | off

enable:
  persist.vendor.adb=true
  Settings.Global.adb_enabled=1

disable:
  persist.vendor.adb=false
```

No matching `Settings.Global.adb_enabled=0` write was recovered in the bounded
disable method. The exact phone-to-glasses invocation, authorization,
request/reply framing, and safe independent replay remain unresolved.

### Protected companion startup and r24.1 result

The accepted native-loader research established:

- 68 external relocation slots captured;
- 29 initializer executions and two unexecuted finalizer targets;
- 11 exact `com.netease.nis.wrapper.MyJni` registrations;
- `MyJni.cl` enter/return and `MyJni.load` entry;
- wrapper `MyApplication` loading and `Application.attach` entry;
- 148 native DEX-source-open events, 12 hashed material candidates, 20,564
  loaded classes, and 9 class loaders in the later startup capture;
- baseline and Frida spawn/resume without an agent survived, while loading a
  zero-hook agent was followed by target death in both tested injection modes.

The r24.1 APK-enhanced review added:

- six APK artifacts scanned with no reported parser errors;
- nine wrapper focus classes attributed to file-backed APK DEX;
- 24 physical `MyJni` invoke observations reduced to eight logical call sites;
- exact DEX call sites for seven of 11 methods;
- `cl` and `load` remained runtime-confirmed startup methods;
- `cp`, `ip`, `ra`, `rp`, and `run` became static-caller-only startup-path
  candidates;
- `d`, `e`, `ed`, and `getEnvInfo` remained caller-unresolved;
- `com.rokid.sprite.global.RealApplication` remained absent from the supplied
  APK census and the accepted 20,564-class runtime inventory.

No user-facing business-feature meaning is proven for the abbreviated
`MyJni` methods.

## Documentation map

- [Documentation index](docs/README.md)
- [Architecture](docs/architecture/README.md)
- [Consumer guides](docs/consumer/README.md)
- [Development resources](docs/development/README.md)
- [Experiments](docs/experiments/README.md)
- [Findings](docs/findings/README.md)
- [Methodology](docs/methodology/README.md)
- [Research](docs/research/README.md)
- [Runbooks](docs/runbooks/README.md)
- [Tests](docs/tests/README.md)
- [References](docs/references/README.md)

## Repository layout

```text
docs/
  architecture/          system architecture and current integration boundary
  consumer/              setup, compatibility, features, troubleshooting
  development/           SDK and community development options
  experiments/           controlled comparison reports
  findings/              consolidated stock-app/device findings
  methodology/           evidence, privacy, and interpretation methods
  research/              native-loader and protected-application publications
  runbooks/              reproducible operator procedures
  tests/                 numbered test reports and master matrix

evidence/
  sanitized/             reviewed public summaries only
  manifests/             hash-only provenance

scripts/
  analysis/              offline analysis helpers
  capture/               capture/workspace helpers
  recovery/              bounded evidence recovery
  research/              public research verification utilities
  safety/                privacy and repository gates
  tests/                 numbered test runners

tools/frida/             generic observation-only templates
templates/               capture and observation templates
fixtures/synthetic/      non-sensitive synthetic fixtures
```

## Privacy and evidence

Raw captures, TLS keys, logs, device/account identifiers, APKs, native
libraries, decompiled trees, recovered proprietary DEX, memory dumps, absolute
runtime addresses, ADB host keys, and partition images do not belong in the
public repository.

See [Evidence handling](docs/methodology/evidence-handling.md) and the
[public evidence index](evidence/README.md).

## Contributing

Contributions are welcome for corrected documentation, consumer guidance,
compatibility reports, reproducible tests, and clean-room development work.
Label claims as **Official**, **Observed**, **Inferred**, or **Unverified**.

Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the
[documentation index](docs/README.md).

## Disclaimer

This project is independent research. Device modification, ADB use, firmware
analysis, and protocol experimentation can cause data loss, service disruption,
or warranty issues. Use only devices, accounts, applications, and evidence you
are authorized to test.
