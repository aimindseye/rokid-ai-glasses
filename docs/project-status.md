# Project Status Through r24.1

This page separates completed observation/research from implementation work that
has not yet been delivered.

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
| Startup materialization and zero-hook trigger boundary | Accepted bounded closure | [Injection comparison](research/native-loader/injection-mode-comparison.md) |
| APK-enhanced class origin and exact DEX caller census | PASS_APK_ENHANCED_REVIEW | [Protected application](research/protected-application/README.md) |

## Partial or unresolved

| Area | Current result |
|---|---|
| Exact Bluetooth GATT/RFCOMM service and message framing | Partial observation; no independent session implementation |
| Pairing/binding authentication contract | Stock behavior observed; independent reproduction not implemented |
| Harmless read-only stock command replay | Not implemented |
| Phone-side Developer Mode request and reply | Exact command, authentication, correlation, and reply semantics unresolved |
| Direct authorization for glasses-side ADB property writes | SELinux/property boundary bounded; direct authorization unresolved |
| `RealApplication` runtime lifecycle | Static candidate absent from supplied APK census and accepted runtime inventory |
| Complete protected business logic | Not recovered |
| Business meaning of abbreviated `MyJni` methods | Not proven |
| Independent Android companion app | Not built |
| Independent USB/Developer Mode toggle | Not built |

## Recommended next engineering phase

A practical next phase should concentrate on:

1. identifying the exact stock phone-to-glasses session transport;
2. reproducing discovery, binding/authentication, and reconnect behavior;
3. replaying one harmless read-only command with verified request/reply
   correlation;
4. tracing the stock Developer Mode action from phone UI to glasses-side
   property executor;
5. adding a guarded toggle only after state query, positive reply, and rollback
   behavior are proven.

The protected-loader research should now be used as supporting context, not as
the primary workstream.

<!-- BEGIN R1.3.3.2.25 PROJECT STATUS -->
## r25 bootstrap status

| Deliverable | Status |
|---|---|
| Stock pairing/reconnect capture harness | Implemented; live evidence pending |
| Bluetooth HCI metadata reduction | Implemented; requires phone bugreport/HCI snoop |
| Developer Mode state/transport correlation | Implemented fail-closed; remote invocation unresolved |
| Read-only Android client | Implemented source; device qualification pending |
| Proprietary CXR session | Not implemented |
| Independent Developer Mode toggle | Disabled and not implemented |

See [connection-protocol research](research/connection-protocol/README.md).
<!-- END R1.3.3.2.25 PROJECT STATUS -->
<!-- BEGIN R1.3.3.2.25.1 PROJECT STATUS -->
## r25.1 stock-session status

| Boundary | Status |
|---|---|
| BLE connection-information source | Closed: characteristic `0x9301` |
| Runtime SDP service attribution | Closed |
| RFCOMM SCN / DLCI / MTU | Closed: 3 / 6 / 990 |
| Stock session establishment sequence | Closed |
| Application framing and authentication semantics | Unresolved |
| Independent replacement-client RFCOMM session | Not implemented |
| Developer Mode remote invocation | Not attempted in the source run |

See [r25.1 findings](research/connection-protocol/r1.3.3.2.25.1-findings.md).
<!-- END R1.3.3.2.25.1 PROJECT STATUS -->
