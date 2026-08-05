# Research Index

<!-- wiki-status: audience=research; applies_to=rokid-ai-glasses-style-non-display; evidence=historical; last_reviewed=2026-08-02 -->

## Page status

| Field | Value |
|---|---|
| Audience | Research |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Historical |
| Last reviewed | 2026-08-02 |

## Evidence rules

- [Research test matrix](test-matrix.md)
- [Evidence levels](evidence-levels.md)
- [General evidence handling](../methodology/evidence-handling.md)
- [Interpretation boundaries](../methodology/interpretation-boundaries.md)

<!-- r27.1.0-canonical-tooling -->
## Canonical research tooling

R27.1 normalizes tooling across the **full research history**, including numbered tests, Tests 19–21/CXR, r22–r24 protected-companion work, r25 connection-protocol work, and shared capture/analysis/evidence utilities.

- [Canonical tooling index](tooling/README.md)
- [Canonical harness](tooling/canonical-harness.md)
- [Legacy and revision-lineage policy](tooling/legacy-lineage-policy.md)
- [R27.1.0 canonicalization record](r27.1.0-whole-repository-canonicalization.md)
- [R27.1.1 r25 validator consolidation](r27.1.1-r25-validator-consolidation.md)

Historical revision paths remain preserved. R27.1.0 introduces the stable front door and lineage inventory; R27.1.1 begins implementation consolidation with 12 tracked r25 validators while retaining their historical files as equivalence oracles. New device testing is paused while canonicalization is incomplete.

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

#### Test 20 final photo path

[Test 20 final photo control and callback publication](../tests/test-20-final-photo-control-callback-publication.md) closes the governed CXR-L one-shot photo work. The accepted implementation retains the image callback strongly and re-registers the same callback after successful service-status qualification before allowing photo arming.

#### Test 21 static Binder boundary

Test 21 completes the static clean-room Binder boundary for the accepted CXR-L `client-l:1.0.1` artifact. The final callback result covers 7 interfaces and 21 methods with 21/21 Stub ↔ Proxy confirmations, all 21 Parcel contracts retained, and 0 transaction mismatches. Authorization, session lifecycle, proprietary service implementation, and end-to-end behavior remain outside the claim.

- [Overview](cxr/test21-static-binder-boundary-overview.md)
- [Findings](cxr/test21-static-binder-boundary-findings.md)
- [Diagrams](cxr/test21-static-binder-boundary-diagrams.md)
- [Callback transaction reference](cxr/test21-callback-transaction-reference.md)

## Current boundary

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

New device testing is paused during R27 repository canonicalization. Custom transmission and captured-payload replay remain disabled until positive reply, authorization/integrity, and rollback semantics are proven.


## CXR-M companion qualification

Test 19 moves the replacement-app work from transport reachability to an
authorized SDK compatibility and ownership qualification. The public repository
contains the harness and interpretation contract; physical results remain
pending until a reviewed run is completed.

- [Test 19 research record](../tests/test-19-r1-cxr-m-maven-and-ownership.md)
- [Developer qualification runbook](../developer/companion-app/test-19-r1-qualification.md)

<!-- test22-final-publication:start -->
## Test 22 independent Wi-Fi boundary

Test 22 closes the phone-independent networking question for the tested ordinary non-privileged paths. CXR-M can temporarily bring up glasses `wlan0`, IPv4, and routing, but that session tears down when the phone is powered off. A separately tested ordinary-app AssistServer Wi-Fi-setting request was accepted and consumed but produced no Android Wi-Fi data-plane transition in the bounded window. The phone-off direct-socket stage was not executed because its independent-route prerequisite disappeared.

- [Final Test 22 record](../tests/test-22-independent-wifi-and-direct-socket.md)
- [Sanitized Test 22 publication](connection-protocol/publication/test22-independent-wifi-boundary.md)
- [Machine-readable evidence chain](connection-protocol/publication/test22-evidence-chain.json)

<!-- test22-final-publication:end -->

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

<!-- r27.1.2-packager-consolidation -->
## R27.1.2 sanitized-evidence packager consolidation

The canonical research harness now includes a profile-driven Test 21 sanitized-evidence packager covering thirty historical packaging revisions, including the final accepted callback-Binder result. Historical packagers remain preserved as lineage/equivalence oracles; no legacy path is removed in this stage.

- [R27.1.2 consolidation record](r27.1.2-test21-packager-consolidation.md)
- [Canonical research harness](tooling/canonical-harness.md)

<!-- r27.1.4-tool-test-consolidation -->
## R27.1.4 tool-test suite consolidation

The canonical harness now provides `rokid-research test run` for 39 historical Tests 19–21 tool-test suites. Thirty-eight current suites are equivalence-qualified; one Test 21 suite is preserved as a deferred missing-fixture historical contract. Historical test source remains unchanged.

- [R27.1.4 consolidation record](r27.1.4-tool-test-suite-consolidation.md)
- [Canonical research harness](tooling/canonical-harness.md)

<!-- r27.1.11-source-contract-snapshot-engine -->
## R27.1.11 source-contract implementation reduction

R27.1.11 replaces the 29 active Test 21 source-contract checker implementations with compatibility shims backed by one canonical accepted-source snapshot engine. The original checker bytes are preserved privately before replacement. The canonical profiles lock the accepted source/file closure and encode source-contract-to-source-contract lineage explicitly rather than executing historical checker Python.

- [R27.1.11 source-contract implementation reduction](r27.1.11-source-contract-snapshot-engine.md)
- [Canonical research harness](tooling/canonical-harness.md)

<!-- r27.1.12-tool-test-oracle-finalization -->
## R27.1.12 tool-test oracle finalization

R27.1.12 finalizes the 38 current Tests 19–21 tool-test files as independent preserved regression oracles rather than rewriting them into the canonical implementation they verify. Exact source locks and canonical execution/test-count gates remain mandatory. The one missing-fixture Test 21 suite remains historical/deferred.

The R27.1 retirement queue is therefore closed with 71 compatibility shims, 38 preserved current regression oracles, four preserved historical/deferred entries, and zero remaining retirement candidates or blockers.

- [R27.1.12 tool-test oracle finalization](r27.1.12-tool-test-oracle-preservation.md)
- [Canonical research harness](tooling/canonical-harness.md)


<!-- r27.2.1-r25-finalization-publication -->
## R27.2.1 r25 finalization and publication-verification framework

R27.2.1 starts the residual host-only consolidation sequence selected by the R27.2.0 census. Seven r25 private-evidence finalizers and six sanitized-publication verifiers are represented by two independent canonical profile-driven engines. The historical thirteen scripts remain byte-unchanged until real-repository equivalence is accepted.

- [R27.2.1 finalization/publication framework](r27.2.1-r25-finalization-publication-framework.md)
- [Canonical research harness](tooling/canonical-harness.md)

<!-- r27.2.2-r25-finalization-publication-reduction -->
## R27.2.2 r25 finalization/publication implementation reduction

After R27.2.1 equivalence, the seven r25 finalizer implementations and six publication-verifier implementations are preserved by exact SHA-256 and their historical filenames are retained as thin compatibility shims backed by the two canonical profile-driven engines.

- [R27.2.2 implementation reduction](r27.2.2-r25-finalization-publication-reduction.md)
- [Canonical research harness](tooling/canonical-harness.md)

<!-- r27.2.4-test21-pcap-parser -->
## R27.2.4 Test 21 PCAP parser framework

The residual-family triage selected the two historical Test 21 PCAP parsers as the strongest genuine host-only duplication remaining after R27.2.2. R27.2.4 introduces one canonical shared parsing core with explicit r3.3.3/r3.3.3.1 profiles while preserving both untracked historical parser files unchanged for behavioral equivalence.

- [R27.2.4 PCAP parser framework](r27.2.4-test21-pcap-parser-framework.md)
- [Canonical research harness](tooling/canonical-harness.md)

- [R27.2.5 Test 21 PCAP parser reduction](r27.2.5-test21-pcap-parser-reduction.md)

- [R27.2.7 Test 19 network analyzer framework](r27.2.7-test19-network-analyzer-framework.md) — profile-driven host-only r1/r2 network-privacy analysis; equivalence-only, with historical analyzers unchanged.

### R27.2.8 FINAL — consolidation closure

[R27.2.8 FINAL](r27.2.8-final-consolidation-closure.md) records the final whole-history disposition: 88 canonicalized implementations, preserved independent regression oracles, four explicitly distinct residual families, zero remaining host-only multi-member consolidation candidates, and readiness for Test 22.

<!-- r27.3-final-publication -->
### R27.3 FINAL PUBLICATION

[R27.3 FINAL PUBLICATION](r27.3-final-publication.md) publishes the accepted R27.2.8 whole-history consolidation as the GitHub baseline before Test 22. The publication is allowlist-driven and excludes private evidence, generated binaries, local paths, credentials, device identifiers, and raw captures.
