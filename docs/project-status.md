# Project Status Through r1.3.3.2.25.2.4

This page separates completed observation and transport qualification from
application-protocol and Developer Mode work that has not yet been delivered.

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
| Stock ADB enable/disable command bytes | Unresolved |
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

The next phase is
`r1.3.3.2.25.3 — Stock ADB Toggle RFCOMM Payload Capture, UIH Frame Attribution, Enable/Disable Differential, and Application-Framing Recovery`.
It should:

1. capture one controlled stock ADB-enable and ADB-disable pair;
2. attribute nonzero RFCOMM UIH payload frames to the exact stock session;
3. establish frame boundaries and stable versus variable fields;
4. prove the enable/disable differential without custom transmission;
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
| `r1.3.3.2.25.2.4` | Final publication and evidentiary supersession |

Earlier results remain preserved as historical evidence. The final r25.2.4
publication is authoritative for the RFCOMM connection-only zero-payload
qualification.
