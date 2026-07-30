# Research Index

## Evidence rules

- [Evidence levels](evidence-levels.md)
- [General evidence handling](../methodology/evidence-handling.md)
- [Interpretation boundaries](../methodology/interpretation-boundaries.md)

## Connection protocol and replacement-app foundation

The accepted r25.2.4 publication proves one independent Android client RFCOMM
open/close lifecycle with SCN `3`, DLCI `6`, MTU `990`, and zero application
bytes in both directions. The accepted r25.3.1.2 and r25.3.1.3 publications
then qualify the existing four-action stock ADB-toggle capture, attribute target
DLCI 6 UIH payloads, prove the enable/disable differential, and close the exact
observed outbound message grammar without replay.

- [Connection-protocol research index](connection-protocol/README.md)
- [Final RFCOMM zero-payload closure](connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md)
- [Machine-readable runtime status](connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json)
- [Methodology](connection-protocol/r1.3.3.2.25.2.4-methodology.md)
- [Limitations](connection-protocol/r1.3.3.2.25.2.4-limitations.md)
- [Evidence identities](connection-protocol/r1.3.3.2.25.2.4-evidence-hashes.txt)
- [Supersession map](connection-protocol/r1.3.3.2.25.2.4-supersession-map.json)
- [Connection-only Android client](../../android-client/README.md)
- [r25.3 pre-repair findings](connection-protocol/r1.3.3.2.25.3-pre-repair-findings.md)
- [r25.3 pre-repair status](connection-protocol/r1.3.3.2.25.3-pre-repair-runtime-status-summary.json)
- [Accepted stock ADB-toggle publication](connection-protocol/stock-adb-toggle/README.md)
- [Integrated stock ADB-toggle runtime status](connection-protocol/stock-adb-toggle/runtime-status-summary.json)
- [Stock ADB-toggle evidence hashes](connection-protocol/stock-adb-toggle/evidence-hashes.txt)
- [Current project status](../project-status.md)

### Current boundary

| Capability | Status |
|---|---|
| Runtime endpoint attribution | Complete in accepted r25.2 scope |
| Independent RFCOMM connection-only client | Implemented and device-qualified |
| Same-attempt matching open/close | Proven |
| HCI application payload | Proven zero in both directions |
| Observed stock ADB-toggle frame grammar | Closed for four qualified messages; broader protocol unresolved |
| Stock local ADB disable/restore property transition | Proven; original transport-loss oracle rejected |
| Stock ADB enable/disable outbound messages | Attributed and decoded for the observed family; replies and authorization unresolved |
| Guarded custom Developer Mode toggle | Not implemented |

The next research phase is independent confirmation and code/reply correlation.
Custom transmission and captured-payload replay remain disabled until positive
reply, authorization/integrity, and rollback semantics are proven.

## OTA boot-chain and offline boot-image research

The read-only boot-chain track matched the live 11,904-byte vbmeta chain to the
exact full OTA and proved that regular ADB shell access cannot read or write the
active boot-chain partitions. It also rejected one contaminated Magisk 30.7
candidate and accepted a repaired candidate offline with the pristine Rokid
kernel and `PREINITDEVICE=metadata`. No image was booted or flashed.

- [Boot-chain research index](boot-chain/README.md)
- [Validated findings](boot-chain/ota-boot-chain-and-offline-magisk-validation.md)
- [Machine-readable status](boot-chain/runtime-status-summary.json)
- [Hash-only provenance](boot-chain/evidence-hashes.txt)

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
| `r1.3.3.2.25.2.4` | Final accepted connection-only publication and supersession |
| `r1.3.3.2.25.3` pre-repair | Rejected physical qualification; local disable/restore semantics retained |
| `r1.3.3.2.25.3.1.1` | Four-action source capture; initial offline parser qualification incomplete |
| `r1.3.3.2.25.3.1.2` | Accepted target-pair qualification, UIH attribution, and differential |
| `r1.3.3.2.25.3.1.3` | Accepted exact observed frame grammar and field-role closure |
| `r1.3.3.2.25.3.1.4` | Sanitized publication integration |
| `r1.3.3.2.25.3.1.4.2` | Full 18-path lineage publication-contract repair |
| Boot-chain audit | Separate read-only live/OTA and offline boot-image validation track |
