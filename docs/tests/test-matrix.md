# Test and Research Matrix

This matrix separates the numbered product/device qualification track from the
protected-companion research-release track. Raw captures remain private; public
reports and evidence are sanitized.

## Numbered product, app, device, and USB tests

| ID | Test | Controlled variable | Status | Public result |
|---|---|---|---|---|
| 00 | First launch without login | App launch | Complete | [Report](00-first-launch.md) |
| 01 | Login | Authentication | Complete | [Report](01-login.md) |
| 02b | Owner unbind/rebind | Account binding | Complete | [Report](02-pairing-and-account-transfer.md) |
| 03a | Firefox TLS canary | MITM validation | PASS | [TLS report](03-tls-interception.md) |
| 03b | Hi Rokid idle/model menu | TLS target app | PASS | [TLS report](03-tls-interception.md) |
| 04a | Select Gemini base model | Model selection | Complete with marker correction | [Report](04-model-selection.md) |
| 04b | Select ChatGPT base model | Model selection | PASS | [Report](04-model-selection.md) |
| 05 | ChatGPT/Gemini prompt routing | Base model | Rokid-mediated routing observed | [Experiment](../experiments/05-gemini-r2-vs-chatgpt-r4.md) |
| 06/06c | Local capability and peripheral/device connection | Phone/device capability | Complete in documented scope | [Report](06c-device-connection.md) |
| 10a–10c4 | Translation architecture series | Mode/context | Complete in documented scope | [Overview](10-translation-overview.md) |
| 11 | Gallery/recording | Media action | Planned | — |
| 12 | Original OTA placeholder | Update action | Superseded by 14B | — |
| 14A | Initial assistant comparison | ChatGPT vs Gemini | Partial pass | [Report](14a-ai-assistant-base-model.md) |
| 14A-r2 | Fresh-session manual voice | ChatGPT vs Gemini | Primary objective PASS | [Report](14a-r2-manual-voice-base-model.md) |
| 14B-D1 | Disconnected baseline | Connection | Complete; raw-PCAP association partial | [Report](14b-firmware-update-discovery.md) |
| 14B-C1 | Connected cold launch | App launch | Automatic OTA request | [Report](14b-firmware-update-discovery.md) |
| 14B-C2 | Open firmware page | Page entry | Additional OTA request | [Report](14b-firmware-update-discovery.md) |
| 14B-C3 | First manual check | Button press | Live OTA request | [Report](14b-firmware-update-discovery.md) |
| 14B-C4 | Repeated manual check | Repeated press | Fresh live OTA request | [Report](14b-firmware-update-discovery.md) |
| 15A | Visual workflow discovery | Capture and transport | PASS — glasses WebP → Bluetooth → OSS → object URL | [Report](15-visual-ai-architecture-routing-retention.md) |
| 15B | Visual routing, retention, context | Route/follow-up/offline history | PASS — route switch, recapture, local cache | [Report](15-visual-ai-architecture-routing-retention.md) |
| 15 | Consolidated visual AI qualification | 15A + 15B | PASS | [Report](15-visual-ai-architecture-routing-retention.md) |
| 16A | Existing-install background lifecycle | Recents/force-stop/relaunch | PASS | [Report](16-android-background-services-package-lineage-data-sharing.md) |
| 16B | Pixel clean install and first run | Package lineage and pre/post-login traffic | PASS | [Report](16-android-background-services-package-lineage-data-sharing.md) |
| 16B-r2 | Clean unauthenticated repair | App-data clear and empty-token check | PASS | [Report](16-android-background-services-package-lineage-data-sharing.md) |
| 16C-r2 | Pairing and paired data sharing | Unpaired/binding/AI/dismissal/relaunch | PASS | [Report](16-android-background-services-package-lineage-data-sharing.md) |
| 16D | Pixel background-mode A/B | Banner unsatisfied vs Unrestricted | PASS | [Report](16-android-background-services-package-lineage-data-sharing.md) |
| 16 | Consolidated Android background/privacy qualification | 16A–16D | PASS in documented scope | [Report](16-android-background-services-package-lineage-data-sharing.md) |
| 17A | Glasses USB ADB discovery | Original debug cable and authorized Mac | PASS | [Report](17-glasses-os-adb-and-network-exposure.md) |
| 17B | Glasses OS/build/boot/storage baseline | Read-only properties and mounts | PASS | [Report](17-glasses-os-adb-and-network-exposure.md) |
| 17C | Local services and TCP 8341 | Processes/services/socket/init metadata | PASS | [Report](17-glasses-os-adb-and-network-exposure.md) |
| 17D | Voice-AI passive interface monitor | One stock voice question | PASS — no glasses IP interface/route observed | [Report](17-glasses-os-adb-and-network-exposure.md) |
| 17E | Visual-AI passive interface monitor | Fresh image; 360 half-second samples | PASS — no glasses IP interface/route observed | [Report](17-glasses-os-adb-and-network-exposure.md) |
| 17F | Static development baseline | APK hashes/Binder/HAL/hardware/network | PASS — privacy gate; 8/8 private APK hashes matched | [Report](17-glasses-os-adb-and-network-exposure.md) |
| 17 | Consolidated glasses OS/ADB/network qualification | 17A–17F | PASS in read-only scope | [Report](17-glasses-os-adb-and-network-exposure.md) |
| 18A | Developer Mode control path | Exact stock OTA static analysis | PASS — key, values, enable/disable property writes recovered | [Finding](../findings/glasses-android-os-and-adb.md#usb-adb-control-path-follow-up) |
| 18B | Runtime domain and property context | Manifest/seapp/policy | PARTIAL — domains/property type bounded; direct authorization unresolved | [Finding](../findings/glasses-android-os-and-adb.md#runtime-domain-and-property-boundary) |
| 18C | Cable and debug-board path | Boot inputs/native/FDT | BOUNDED — debug-board evidence; direct ADB/cable-ID path not proven | [Finding](../findings/glasses-android-os-and-adb.md#cable-and-debug-board-boundary) |
| 18D | Repair-app and recovery boundaries | Static reachability/recovery | BOUNDED — no safe exported setter; phone replay blocked | [Finding](../findings/glasses-android-os-and-adb.md#repair-app-feasibility) |
| 18 | USB ADB control-path follow-up | 18A–18D | PASS in static/offline scope; runtime invocation unresolved | [Sanitized summary](../../evidence/sanitized/glasses-os-services/usb-adb-control-summary.txt) |

## Research and implementation releases

| Release | Scope | Accepted result | Public result |
|---|---|---|---|
| `r1.3.3.2.22.1.1` | Native loader, secondary runtime, relocations, callbacks, exact RegisterNatives attribution, Java handoff | `PASS_RECOVERED`; original six blockers closed in their bounded definitions | [Validated findings](../research/native-loader/r1.3.3.2.22.1.1-findings.md) |
| `r1.3.3.2.23.5.1.6.3` | Standalone external probe and post-injection death-race semantics | Both injected trials accepted; collection/retrieval/retention validated | [Injection comparison](../research/native-loader/injection-mode-comparison.md) |
| `r1.3.3.2.23.5.1.7.1` | Historical preservation and additive startup/trigger publication | Native-runtime and later 647-event evidence sets preserved separately | [Native-loader index](../research/native-loader/README.md) |
| `r1.3.3.2.24` | RealApplication lifecycle, class origin, and MyJni caller classification | `PASS_BOUNDED_CLOSURE`; RealApplication runtime confirmation remained false | [Protected application](../research/protected-application/README.md) |
| `r1.3.3.2.24.1` | Six-APK differential and exact DEX caller census | `PASS_APK_ENHANCED_REVIEW`; 24 physical observations → 8 logical sites; 7/11 methods with exact DEX sites | [Accepted review](../research/protected-application/publication/accepted-evidence-review.json) |
| `r1.3.3.2.25` | Stock capture and minimal-client bootstrap | `PASS_BOOTSTRAP_READY` | [Connection-protocol index](../research/connection-protocol/README.md) |
| `r1.3.3.2.25.1` | Stock endpoint provisioning and RFCOMM establishment | `PASS_STOCK_SESSION_ESTABLISHMENT_CLOSED` | [r25.1 findings](../research/connection-protocol/r1.3.3.2.25.1-findings.md) |
| `r1.3.3.2.25.2` | Independent BLE provisioning and connection-only RFCOMM client | Implementation accepted; later phases supplied final device proof | [r25.2 findings](../research/connection-protocol/r1.3.3.2.25.2-findings.md) |
| `r1.3.3.2.25.2.2.2` | Strict private-handoff connection-only qualification | Historical bounded socket-open/zero-I/O result | [Qualification](../research/connection-protocol/r1.3.3.2.25.2.2.2-rfcomm-connection-only-qualification.md) |
| `r1.3.3.2.25.2.3.2` | Strict private-handoff, single-tap lifecycle, and HCI DLCI census | `PASS_FULL_RFCOMM_HCI_ZERO_PAYLOAD_CLOSURE` | [Integration findings](../research/connection-protocol/r1.3.3.2.25.2.3.2-strict-private-handoff-integration.md) |
| `r1.3.3.2.25.2.4` | Final publication, evidence-hash promotion, and prior bounded-result supersession | `PASS_FINAL_RFCOMM_ZERO_PAYLOAD_PUBLICATION_INTEGRATION` | [Final publication](../research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md) |
| `r1.3.3.2.25.3` pre-repair | Stock ADB toggle physical run and semantic disable/restore observation | `REJECTED_INVALID_DISABLE_ORACLE`; property transition proven, payload qualification not reached | [Pre-repair findings](../research/connection-protocol/r1.3.3.2.25.3-pre-repair-findings.md) |
| Boot-chain audit | Exact live/OTA vbmeta correspondence, shell partition boundary, and repaired Magisk image offline validation | `PASS_OFFLINE_REPAIRED_CANDIDATE`; no boot or flash | [Boot-chain findings](../research/boot-chain/ota-boot-chain-and-offline-magisk-validation.md) |

Repair-only `.1.x` releases remain in the detailed
[connection-protocol index](../research/connection-protocol/README.md) and the
[supersession map](../research/connection-protocol/r1.3.3.2.25.2.4-supersession-map.json).

## Capability status after r1.3.3.2.25.3 pre-repair

| Goal | Status |
|---|---|
| Observe stock pairing, AI, visual, OTA, lifecycle, and device behavior | Substantially complete in documented scope |
| Know glasses-side Developer Mode key/property effects | Complete statically |
| Attribute the runtime Bluetooth endpoint | Complete in accepted r25.2 scope |
| Open and close the target RFCOMM transport independently | Complete and device-qualified |
| Prove zero application payload for the connection-only attempt | Complete by lossless HCI census |
| Recover CXR/application framing and request/reply semantics | Unresolved |
| Prove stock local disable/restore property effects | Complete; transport disappearance is not required |
| Attribute stock ADB enable/disable command bytes | Unresolved |
| Match live vbmeta chain to exact OTA | Complete for the 11,904-byte chain |
| Validate repaired Magisk boot candidate offline | Complete; no device boot or flash |
| Build a guarded independent Developer Mode toggle | Not implemented |

See [project status](../project-status.md) for the current engineering boundary.
