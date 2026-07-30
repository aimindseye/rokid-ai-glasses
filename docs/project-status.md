# Project Status Through r1.3.3.2.25.3.1.3

This page separates completed observation and transport qualification from
application-protocol, Developer Mode, and device-modification work that has not yet been delivered.

## Completed or substantially closed

| Area | Status | Evidence |
|---|---|---|
| First launch, login, pairing, model routing | Complete in documented scope | [Test matrix](tests/test-matrix.md) |
| Translation architecture and routing | Complete in documented scope | [Translation tests](tests/10-translation-overview.md) |
| Voice assistant route comparison | PASS | [Test 14A-r2](tests/14a-r2-manual-voice-base-model.md) |
| OTA check triggers and manifest behavior | PASS | [Test 14B](tests/14b-firmware-update-discovery.md) |
| Visual capture, upload, routing, follow-up, retention | PASS | [Test 15](tests/15-visual-ai-architecture-routing-retention.md) |
| App lifecycle, background services, package lineage | PASS | [Test 16](tests/16-android-background-services-package-lineage-data-sharing.md) |
| Glasses Android, USB ADB, local services, passive network exposure | PASS | [Test 17](tests/17-glasses-os-adb-and-network-exposure.md) |
| Developer Mode key and property-write semantics | PASS statically | [USB ADB finding](findings/glasses-android-os-and-adb.md#usb-adb-control-path-follow-up) |
| Protected native-loader and Java handoff | Accepted bounded closure | [Native-loader research](research/native-loader/README.md) |
| APK-enhanced class origin and exact DEX caller census | `PASS_APK_ENHANCED_REVIEW` | [Protected application](research/protected-application/README.md) |
| Runtime Bluetooth endpoint attribution | Complete in accepted r25.2 scope | [Connection-protocol index](research/connection-protocol/README.md) |
| Independent Android connection-only RFCOMM client | Implemented and device-qualified | [Android client](../android-client/README.md) |
| Same-attempt RFCOMM client lifecycle | PROVEN | [Final closure](research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md) |
| HCI zero-application-payload census | PROVEN: TX 0 bytes, RX 0 bytes | [Runtime status](research/connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json) |
| Stock ADB disable/restore local semantics | PROVEN across two cycles; final state restored; transport disappearance not required | [Stock ADB-toggle findings](research/connection-protocol/stock-adb-toggle/findings.md) |
| Target-pair-scoped RFCOMM UIH attribution | ACCEPTED; 8 target DLCI 6 frames, 7 payload frames, 0 target-pair parse errors | [r25.3.1.2 runtime status](research/connection-protocol/stock-adb-toggle/r25.3.1.2-runtime-status-summary.json) |
| Exact observed ADB-toggle frame grammar | ACCEPTED; lengths, field order, sequence candidate, discriminator, and structured state role closed | [r25.3.1.3 runtime status](research/connection-protocol/stock-adb-toggle/r25.3.1.3-runtime-status-summary.json) |
| Live/OTA vbmeta-chain correspondence | PASS for exact 11,904-byte chain | [Boot-chain research](research/boot-chain/README.md) |
| Repaired Magisk boot candidate | ACCEPTED offline only; no boot or flash | [Offline validation](research/boot-chain/ota-boot-chain-and-offline-magisk-validation.md) |

## Current replacement-app boundary

| Capability | Current result |
|---|---|
| BLE provisioning and runtime endpoint acquisition | Complete for the accepted connection-only workflow |
| RFCOMM service/channel identity | Complete: SCN `3`, DLCI `6`, MTU `990` |
| Independent RFCOMM open/close | Complete and hardware-qualified |
| Lossless HCI lifecycle correlation | Complete: SABM/UA and DISC/UA |
| Application bytes during accepted connection-only attempt | Proven zero in both directions |
| Binding/session-authentication contract | Stock and strict-handoff behavior observed; general independent reproduction not established |
| Observed stock ADB-toggle frame grammar | Closed for the four qualified messages; broader CXR grammar unresolved |
| Reply correlation, authorization, integrity, checksum, and session binding | Unresolved |
| Stock ADB enable/disable outbound messages | Attributed and decoded for the observed family; independent acceptance and replies unresolved |
| r25.3 original physical qualification | Rejected because the runner required transport disappearance after stock disable |
| Read-only application command decoder | Implemented host-only for the observed family; replay remains prohibited and unimplemented |
| Guarded independent USB/Developer Mode toggle | Not implemented |
| Full replacement Android companion | Not built; transport foundation is available |

## Accepted conclusion

```text
RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS
PASS_EXISTING_CAPTURE_TARGET_PAIR_SCOPED_RFCOMM_QUALIFICATION_UIH_DIFFERENTIAL_AND_BOUNDED_FRAMING_CLOSURE
PASS_EXISTING_CAPTURE_EXACT_ADB_TOGGLE_APPLICATION_FRAME_GRAMMAR_NESTED_LENGTH_SEQUENCE_DISCRIMINATOR_AND_STRUCTURED_PAYLOAD_ROLE_CLOSURE
```

The connection-only result remains authoritative for independent zero-payload
transport qualification. The later accepted stock capture establishes the
outbound ADB-toggle message family for four qualified actions. Neither result
authorizes an independent command sender.

## Recommended next engineering phase

The next phase should remain read-only and correlation-first:

1. repeat the four-action stock capture on an independent session or build;
2. correlate the observed envelope, discriminator, and sequence candidate with recovered constructors or native transforms;
3. recover positive reply and acknowledgement semantics;
4. identify authorization, integrity, checksum, and session-binding fields;
5. prove a deterministic failure and rollback model before implementing any sender;
6. keep custom RFCOMM transmission and captured-payload replay disabled until those gates pass.

## Research progression and supersession

| Release | Current standing |
|---|---|
| `r1.3.3.2.25` | Historical bootstrap: stock capture and minimal probe foundation |
| `r1.3.3.2.25.1` | Historical stock-session transport establishment closure |
| `r1.3.3.2.25.2` | Independent connection-only implementation track |
| `r1.3.3.2.25.2.2.2` | Historical bounded socket-open/zero-I/O result |
| `r1.3.3.2.25.2.2.2.1.3` | Historical bounded lifecycle-only conclusion for the older archive |
| `r1.3.3.2.25.2.3.2` | Authoritative instrumented runtime evidence |
| `r1.3.3.2.25.2.4` | Final accepted connection-only publication and evidentiary supersession |
| `r1.3.3.2.25.3` pre-repair | Historical rejected run; local property transition retained |
| `r1.3.3.2.25.3.1.1` | Accepted four-action physical source capture; initial offline analysis blocked by unscoped non-target-CID errors |
| `r1.3.3.2.25.3.1.2` | Accepted target-pair-scoped offline salvage, UIH attribution, and enable/disable differential |
| `r1.3.3.2.25.3.1.3` | Accepted exact observed frame grammar and field-role closure |
| `r1.3.3.2.25.3.1.4` | Current sanitized repository publication integration |
| Boot-chain audit | Read-only live/OTA correspondence and offline repaired-image validation; separate from connection-protocol qualification |

Earlier results remain preserved as historical evidence. The final r25.2.4
publication is authoritative for the independent connection-only zero-payload
qualification. The accepted r25.3.1.2 and r25.3.1.3 publications are
authoritative for the observed stock ADB-toggle message family.

## Boot-chain and modification boundary

The exact running build matched the full OTA. The live 11,904-byte vbmeta digest
matched the OTA-derived chain, while regular ADB shell access to active
boot-chain partitions remained denied. A repaired Magisk 30.7 image was accepted
for offline research only with the pristine kernel and
`PREINITDEVICE=metadata`. It is not OEM-signed, was not booted or flashed, and
does not authorize a device-modification step.
