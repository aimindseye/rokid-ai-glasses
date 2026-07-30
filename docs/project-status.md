# Project Status Through r1.3.3.2.25.3 Pre-Repair

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
| Stock ADB disable/restore local semantics | PROVEN; original r25.3 transport-loss oracle rejected | [Pre-repair findings](research/connection-protocol/r1.3.3.2.25.3-pre-repair-findings.md) |
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
| CXR/application framing | Unresolved |
| Request IDs, integrity/authentication fields, and reply correlation | Unresolved |
| Stock ADB enable/disable command bytes | Unresolved; the local property effects are proven |
| r25.3 original physical qualification | Rejected because the runner required transport disappearance after stock disable |
| Read-only application command decoder/replay | Not implemented |
| Guarded independent USB/Developer Mode toggle | Not implemented |
| Full replacement Android companion | Not built; transport foundation is available |

## Accepted conclusion

```text
RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS
```

The result is scoped to one connection-only Android client attempt. It proves
that the custom client can reach and safely close the target RFCOMM transport;
it does not identify or authorize an application-layer command.

## Recommended next engineering phase

The next phase is the repaired
`r1.3.3.2.25.3.1 — Stock ADB Toggle RFCOMM Payload Capture with a Semantic Disable Oracle`.
It should:

1. capture one controlled stock ADB-enable and ADB-disable pair;
2. attribute nonzero RFCOMM UIH payload frames to the exact stock session;
3. establish frame boundaries and stable versus variable fields;
4. prove the enable/disable differential without requiring immediate USB transport loss;
5. correlate the frames with recovered Java/native constructors and transforms;
6. implement a decoder before any sender or replay;
7. keep independent Developer Mode writes disabled until positive reply and
   rollback behavior are proven.

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
| `r1.3.3.2.25.3` pre-repair | Physical run rejected due invalid disable oracle; local property transition retained as proven evidence |
| Boot-chain audit | Read-only live/OTA correspondence and offline repaired-image validation; separate from connection-protocol qualification |

Earlier results remain preserved as historical evidence. The final r25.2.4
publication is authoritative for the RFCOMM connection-only zero-payload
qualification.

## Boot-chain and modification boundary

The exact running build matched the full OTA. The live 11,904-byte vbmeta digest
matched the OTA-derived chain, while regular ADB shell access to active
boot-chain partitions remained denied. A repaired Magisk 30.7 image was accepted
for offline research only with the pristine kernel and
`PREINITDEVICE=metadata`. It is not OEM-signed, was not booted or flashed, and
does not authorize a device-modification step.
