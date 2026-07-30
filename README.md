# Rokid AI Glasses Style — Consumer, Developer, and Research Guide

![Product](https://img.shields.io/badge/Product-Rokid%20AI%20Glasses%20Style-111827)
![Form factor](https://img.shields.io/badge/Form%20factor-Display--free-0284c7)
![Coverage](https://img.shields.io/badge/Coverage-Tests%2000%E2%80%9318%20%7C%20r25.3.1.3%20accepted-7c3aed)
![Evidence](https://img.shields.io/badge/Evidence-Sanitized%20and%20reproducible-16a34a)

An independent, community-maintained guide to the **display-free Rokid AI
Glasses Style**, the **Hi Rokid** Android companion application, and the
validated research completed through **Test 18**, the accepted
**r1.3.3.2.25.2.4** transport publication, the accepted **r1.3.3.2.25.3.1.2** target-pair qualification, the accepted
**r1.3.3.2.25.3.1.3** exact observed-frame grammar, and the read-only OTA
boot-chain audit.

> Unofficial community project. Not affiliated with Rokid.

## Current state in one page

The project has established four complementary layers:

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
   caller census. It did not recover the complete protected application.
4. **Independent transport foundation.** The r25.2 workstream attributed the
   runtime endpoint, implemented a strict connection-only Android RFCOMM client,
   correlated one client open/close attempt, and proved by a lossless HCI census
   that the target DLCI carried zero application bytes in both directions.
5. **Stock-toggle protocol and boot-chain qualification.** The repaired stock
   capture completed two disable and two enable actions, preserved a usable
   control channel, restored the final state, attributed seven payload-bearing
   target DLCI 6 frames, and closed the exact observed outbound ADB-toggle
   grammar without replay. A separate read-only audit matched the live
   11,904-byte vbmeta chain to the exact OTA and validated one repaired Magisk
   boot image offline without booting or flashing it.

### Replacement-app readiness

| Capability | Current status | Best current reference |
|---|---|---|
| Stock pairing and cloud workflow observation | Substantially complete | [Test matrix](docs/tests/test-matrix.md) |
| Glasses Android/ADB/local-service baseline | Complete in read-only scope | [Test 17](docs/tests/17-glasses-os-adb-and-network-exposure.md) |
| Developer Mode property semantics | Static writes and runtime disable/restore transition proven | [USB ADB finding](docs/findings/glasses-android-os-and-adb.md#runtime-stock-toggle-semantics-and-observed-message-grammar) |
| Runtime Bluetooth endpoint attribution | Complete in the accepted r25.2 scope | [Connection-protocol research](docs/research/connection-protocol/README.md) |
| Independent connection-only RFCOMM client | Implemented and device-qualified | [Android client](android-client/README.md) |
| Same-attempt RFCOMM open/close lifecycle | Proven | [Final closure publication](docs/research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md) |
| HCI application-payload census | Proven: TX 0 bytes, RX 0 bytes | [Runtime status](docs/research/connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json) |
| Observed stock ADB-toggle application framing | Exact four-message grammar closed; broader authentication and reply semantics unresolved | [Stock ADB-toggle publication](docs/research/connection-protocol/stock-adb-toggle/README.md) |
| Stock ADB enable/disable outbound message family | UIH attribution, repeated differential, lengths, discriminator, and structured state role proven; reply/authorization unresolved | [Stock ADB-toggle findings](docs/research/connection-protocol/stock-adb-toggle/findings.md) |
| Live/OTA boot-chain correspondence | Proven for the 11,904-byte vbmeta chain; active partitions remain unreadable to shell | [Boot-chain research](docs/research/boot-chain/README.md) |
| Repaired Magisk boot candidate | Accepted offline only; pristine kernel, `PREINITDEVICE=metadata`, no device boot/flash | [Offline validation](docs/research/boot-chain/ota-boot-chain-and-offline-magisk-validation.md) |
| Guarded independent Developer Mode toggle | Not implemented | [Project status](docs/project-status.md) |

The transport-feasibility question is closed for the accepted connection-only
attempt. The immediate engineering gap is now **independent protocol confirmation and
reply safety**: correlate the observed grammar with code, recover positive reply
and authorization/integrity semantics, repeat the capture independently, and
only then consider a guarded sender with explicit rollback.

## Start here

| Goal | Page |
|---|---|
| Understand what is proven and what remains | [Project status](docs/project-status.md) |
| Review the final RFCOMM zero-payload proof | [Final closure publication](docs/research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md) |
| Inspect the machine-readable transport result | [Runtime status](docs/research/connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json) |
| Review the accepted stock ADB-toggle protocol result | [Stock ADB-toggle publication](docs/research/connection-protocol/stock-adb-toggle/README.md) |
| Review the rejected r25.3 pre-repair lineage | [Pre-repair findings](docs/research/connection-protocol/r1.3.3.2.25.3-pre-repair-findings.md) |
| Review live/OTA boot-chain and offline Magisk validation | [Boot-chain research](docs/research/boot-chain/README.md) |
| Follow the connection-protocol research | [Connection-protocol index](docs/research/connection-protocol/README.md) |
| Inspect the connection-only Android client | [Android client](android-client/README.md) |
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
- Boot properties reported orange/unlocked state. The live bootloader-reported
  11,904-byte vbmeta digest matched the exact OTA-derived vbmeta chain. The
  regular ADB shell could not read or write the active boot-chain partitions.
  This project did not unlock, root, flash, relock, or modify partitions.
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

### Independent RFCOMM transport foundation

The accepted r25.2.4 publication proves one independently initiated Android
client-side RFCOMM connection-only lifecycle. A strict private handoff supplied
the runtime endpoint; the client opened and closed exactly once with protocol
invariants SCN `3`, DLCI `6`, and MTU `990`. The correlated HCI stream contained
SABM/UA and DISC/UA control boundaries and no application-bearing UIH frames:
TX `0` bytes and RX `0` bytes.

This result proves transport reachability and a safe zero-payload lifecycle. It
does **not** identify an application-layer protocol or authorize a Developer
Mode command. See the [final publication](docs/research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md),
[methodology](docs/research/connection-protocol/r1.3.3.2.25.2.4-methodology.md),
[limitations](docs/research/connection-protocol/r1.3.3.2.25.2.4-limitations.md),
[evidence hashes](docs/research/connection-protocol/r1.3.3.2.25.2.4-evidence-hashes.txt),
and [supersession map](docs/research/connection-protocol/r1.3.3.2.25.2.4-supersession-map.json).

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
disable method. The accepted repaired capture completed two stock disable and
two stock enable actions. The semantic oracle used `persist.vendor.adb` plus the
stock UI switch, did not require transport disappearance, kept the control
channel usable, and restored the final state to `on`.

Offline HCI analysis attributed one outbound action-specific message to each
window. Disable messages are 97 bytes; enable messages are 96 bytes. The exact
observed family has self-inclusive outer and nested lengths, stable field order,
a one-byte monotonic transaction/sequence candidate, a repeat-stable action
discriminator, and structured `on`/`off` state correlated with the stock UI and
vendor property. Reply semantics, authorization/integrity behavior, safe custom
transmission, and rollback remain unresolved. See the
[accepted stock ADB-toggle publication](docs/research/connection-protocol/stock-adb-toggle/README.md).

### Read-only boot-chain and offline Magisk result

The running build and exact full OTA matched, including a byte-identical
11,904-byte vbmeta chain. The stock boot image is header version 3 and contains
the generic ramdisk. A prior Magisk 30.7 candidate was rejected because it
carried a foreign `PREINITDEVICE=sda8` value and a false-positive Samsung DEFEX
kernel patch. The repaired offline candidate uses `PREINITDEVICE=metadata`,
restores the pristine Rokid kernel byte-for-byte, and passes local hash-footer
verification with AVB algorithm `NONE`. The repaired image is not OEM-signed,
was not booted or flashed, and is not published. See the
[boot-chain research](docs/research/boot-chain/README.md).

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
  research/              protected startup and connection-protocol publications
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

<!-- BEGIN R1.3.3.2.25.2.4 CURRENT TRANSPORT STATUS -->
## Current connection-protocol result — r1.3.3.2.25.2.4

Documentation navigation and readiness status were aligned in
`r1.3.3.2.25.2.4.1`. The authoritative connection-only result remains
`RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS`.
The independent Android client reached the runtime RFCOMM endpoint, completed
one matching open/close lifecycle, and exchanged zero application bytes on the
target DLCI. Earlier bounded r25.2 results remain historical evidence and are
superseded for this qualification question.

- [Final publication](docs/research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md)
- [Runtime status](docs/research/connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json)
- [Methodology](docs/research/connection-protocol/r1.3.3.2.25.2.4-methodology.md)
- [Limitations](docs/research/connection-protocol/r1.3.3.2.25.2.4-limitations.md)
- [Evidence identities](docs/research/connection-protocol/r1.3.3.2.25.2.4-evidence-hashes.txt)
- [Supersession map](docs/research/connection-protocol/r1.3.3.2.25.2.4-supersession-map.json)

Application framing, command authentication, the stock ADB enable/disable
payloads, reply semantics, and a guarded independent Developer Mode toggle
remain unresolved.
<!-- END R1.3.3.2.25.2.4 CURRENT TRANSPORT STATUS -->

<!-- BEGIN R1.3.3.2.25.3.1.4 CURRENT STOCK-TOGGLE STATUS -->
## Current stock ADB-toggle result — r1.3.3.2.25.3.1.2 and r1.3.3.2.25.3.1.3

The accepted repaired stock capture completed two disable and two enable
transitions, restored the final state, and retained a usable control channel.
Target-pair-scoped HCI qualification recovered eight target DLCI 6 frames,
including seven payload-bearing frames. Two malformed candidates on a non-target
dynamic CID remain private diagnostics and do not invalidate the clean target
pairs.

The four action-specific outbound messages prove an enable/disable differential
and one exact observed message family: 97-byte disable, 96-byte enable,
self-inclusive outer and nested lengths, stable field order, a one-byte
monotonic transaction/sequence candidate, repeat-stable discriminator, and
structured state correlated with the stock UI and `persist.vendor.adb`.

No custom transmission or captured-payload replay was attempted. Reply semantics,
authorization/integrity behavior, independent code correlation, and guarded
rollback remain unresolved.

- [Accepted publication](docs/research/connection-protocol/stock-adb-toggle/README.md)
- [Integrated runtime status](docs/research/connection-protocol/stock-adb-toggle/runtime-status-summary.json)
- [Evidence hashes](docs/research/connection-protocol/stock-adb-toggle/evidence-hashes.txt)
- [Historical pre-repair findings](docs/research/connection-protocol/r1.3.3.2.25.3-pre-repair-findings.md)
<!-- END R1.3.3.2.25.3.1.4 CURRENT STOCK-TOGGLE STATUS -->
