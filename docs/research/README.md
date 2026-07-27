# Research Index

## Evidence rules

- [Evidence levels](evidence-levels.md)
- [General evidence handling](../methodology/evidence-handling.md)
- [Interpretation boundaries](../methodology/interpretation-boundaries.md)

## Connection protocol and replacement-app foundation

The current transport result is
`RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS`.
The accepted r25.2.4 publication proves one independent Android client RFCOMM
open/close lifecycle with SCN `3`, DLCI `6`, MTU `990`, and zero application
bytes in both directions. Application framing and the ADB command remain open.

- [Connection-protocol research index](connection-protocol/README.md)
- [Final RFCOMM zero-payload closure](connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md)
- [Machine-readable runtime status](connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json)
- [Methodology](connection-protocol/r1.3.3.2.25.2.4-methodology.md)
- [Limitations](connection-protocol/r1.3.3.2.25.2.4-limitations.md)
- [Evidence identities](connection-protocol/r1.3.3.2.25.2.4-evidence-hashes.txt)
- [Supersession map](connection-protocol/r1.3.3.2.25.2.4-supersession-map.json)
- [Connection-only Android client](../../android-client/README.md)
- [Current project status](../project-status.md)

### Current boundary

| Capability | Status |
|---|---|
| Runtime endpoint attribution | Complete in accepted r25.2 scope |
| Independent RFCOMM connection-only client | Implemented and device-qualified |
| Same-attempt matching open/close | Proven |
| HCI application payload | Proven zero in both directions |
| CXR/application framing | Unresolved |
| Stock ADB enable/disable command | Unresolved |
| Guarded custom Developer Mode toggle | Not implemented |

The next research phase is a controlled stock ADB-toggle payload capture and
enable/disable differential. It must decode before any custom transmission.

## Protected companion startup

### Native-loader track — r22 through r23

Start with the [native-loader research index](native-loader/README.md). It
preserves the historical r22 native-runtime closure and the later r23
startup-materialization and zero-hook injection-trigger publication as separate
evidence sets.

### Protected-application track — r24 and r24.1

Start with the [protected-application review](protected-application/README.md).
The accepted r24.1 result includes six-APK class-origin attribution and an exact
DEX caller census while keeping `RealApplication` and business-feature
semantics explicitly unresolved.

These protected-startup publications support application-protocol recovery but
do not by themselves identify the stock ADB command.

## Connection-protocol release progression

| Release | Standing |
|---|---|
| `r1.3.3.2.25` | Bootstrap capture and minimal-client foundation |
| `r1.3.3.2.25.1` | Stock transport establishment closure |
| `r1.3.3.2.25.2` | Independent connection-only client implementation |
| `r1.3.3.2.25.2.2.2` | Historical bounded socket-open result |
| `r1.3.3.2.25.2.3.2` | Authoritative instrumented HCI evidence |
| `r1.3.3.2.25.2.4` | Final publication and supersession |
