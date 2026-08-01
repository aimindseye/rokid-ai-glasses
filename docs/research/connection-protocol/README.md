# Stock Connection Protocol and Minimal Companion Research

This directory contains the implementation-focused connection-protocol track
after Tests 00–18 and the protected-companion work through r24.1.

## Current authoritative state

| Boundary | Status |
|---|---|
| Stock `CXRControl/startBTPairing` operation | Proven statically |
| Glasses-side Developer Mode key and property effects | Proven statically |
| Runtime Bluetooth endpoint attribution | Complete in accepted r25.2 scope |
| RFCOMM SCN / DLCI / MTU | Complete: `3` / `6` / `990` |
| Independent Android connection-only client | Implemented and device-qualified |
| Same-attempt matching open/close | Proven |
| Lossless HCI DLCI lifecycle | Proven |
| Application payload in accepted connection-only attempt | TX `0` bytes / RX `0` bytes |
| Pairing/binding authentication contract | General independent reproduction unresolved |
| Observed stock ADB-toggle frame grammar | Closed for four qualified messages |
| Reply, authorization, integrity, and broader CXR semantics | Unresolved |
| Stock local disable/restore property transition | Proven; existing USB transport may remain alive |
| Stock ADB enable/disable outbound message family | Attributed and decoded in accepted r25.3.1.2/.3 scope |
| r25.3 original physical qualification | Rejected due invalid transport-loss oracle |
| Independent Developer Mode toggle | Disabled and not implemented |

## Final r25.2.4 publication

The authoritative conclusion is
`RFCOMM_CLIENT_FULL_ZERO_PAYLOAD_RUNTIME_CLOSURE_PROVEN_BY_HCI_DLCI_CENSUS`.
A strict private handoff provisioned one ready client attempt before the measured
interval. HCI showed SABM/UA open, DISC/UA close, zero drops or truncation, and
no application-bearing UIH frames on DLCI 6.

- [Final publication](r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md)
- [Runtime status](r1.3.3.2.25.2.4-runtime-status-summary.json)
- [Methodology](r1.3.3.2.25.2.4-methodology.md)
- [Limitations](r1.3.3.2.25.2.4-limitations.md)
- [Evidence identities](r1.3.3.2.25.2.4-evidence-hashes.txt)
- [Supersession map](r1.3.3.2.25.2.4-supersession-map.json)
- [Publication integration method](r1.3.3.2.25.2.4-publication-integration-method.md)

## Accepted stock ADB-toggle publication

The pre-repair r25.3 run remains a rejected historical result because its
disable oracle required transport disappearance. The repaired r25.3.1.1 source
capture completed two disable and two enable actions with semantic property/UI
oracles, a usable control channel, and final-state restoration.

The accepted r25.3.1.2 offline analysis scopes RFCOMM parser qualification to
handle/CID pairs that actually yield DLCI 6 frames, retains two non-target-CID
errors privately, attributes seven payload-bearing target frames, and proves the
repeated enable/disable differential. The accepted r25.3.1.3 analysis closes the
exact observed outbound grammar, length fields, one monotonic sequence candidate,
action discriminator, and structured state role.

- [Current stock ADB-toggle publication](stock-adb-toggle/README.md)
- [Lineage](stock-adb-toggle/lineage.md)
- [Findings](stock-adb-toggle/findings.md)
- [Methodology](stock-adb-toggle/methodology.md)
- [Limitations](stock-adb-toggle/limitations.md)
- [Integrated runtime status](stock-adb-toggle/runtime-status-summary.json)
- [Evidence hashes](stock-adb-toggle/evidence-hashes.txt)
- [Historical pre-repair findings](r1.3.3.2.25.3-pre-repair-findings.md)

## Accepted CXR-L capability and event publications

Test 20 r1.2 publishes the reviewed and corrected static census for
`com.rokid.cxr:client-l:1.0.1`. Its immutable runtime boundary contains nine
descriptor-exact members and two Hi Rokid components. The original over-broad
Test 20 r1 classification remains withdrawn.

Test 20 r2.2 adds a separate descriptor-exact runtime qualification delta for
`onGlassAiAssistStart()V` and `onGlassAiAssistStop()V`. One governed attempt
observed two ordered cycles, zero duplicate starts, zero out-of-order stops,
clean disconnect, and Hi Rokid recovery. Across the two accepted publications,
the combined CXR-L runtime-qualified member boundary is eleven.

- [Corrected machine-readable census](publication/test20-r1-cxr-l-capability-census.json)
- [Corrected human-readable census](publication/test20-r1-cxr-l-capability-census.md)
- [Static-census evidence identities](publication/test20-r1-cxr-l-evidence-hashes.txt)
- [AI-assist callback summary JSON](publication/test20-r2-cxr-l-event-summary.json)
- [AI-assist callback summary](publication/test20-r2-cxr-l-event-summary.md)
- [AI-assist callback evidence identities](publication/test20-r2-cxr-l-evidence-hashes.txt)
- [Test 20 r1.2 publication closure](../../tests/test-20-r1-2-cxr-l-final-publication.md)
- [Test 20 r2.2 publication closure](../../tests/test-20-r2-2-final-ai-assist-callback-publication.md)

## Implementation and research history

- [Known boundaries](known-boundaries.md)
- [Capture methodology](capture-methodology.md)
- [Developer Mode attribution](developer-mode-attribution.md)
- [Minimal client status](minimal-client-status.md)
- [r25.1 stock-session findings](r1.3.3.2.25.1-findings.md)
- [r25.2 connection-only findings](r1.3.3.2.25.2-findings.md)
- [r25.2.1 power-state BLE attribution](r1.3.3.2.25.2.1-findings.md)
- [r25.2.2 stock-assisted attribution](r1.3.3.2.25.2.2-findings.md)
- [r25.2.2.1 cached-runtime attribution](r1.3.3.2.25.2.2.1-cached-runtime-endpoint-attribution.md)
- [r25.2.2.2 strict connection-only qualification](r1.3.3.2.25.2.2.2-rfcomm-connection-only-qualification.md)
- [r25.2.3 HCI capture design](r1.3.3.2.25.2.3-instrumented-rfcomm-hci-zero-payload-capture.md)
- [r25.2.3.2 strict-handoff integration](r1.3.3.2.25.2.3.2-strict-private-handoff-integration.md)
- [r25.3.1 semantic-oracle repair](r1.3.3.2.25.3.1-stock-adb-toggle-semantic-oracle-repair-rfcomm-payload-capture.md)
- [r25.3.1.1 operator-arm sequencing repair](r1.3.3.2.25.3.1.1-stock-adb-toggle-semantic-oracle-repair-rfcomm-payload-capture.md)
- [r25.3.1.2 target-pair-scoped offline salvage](r1.3.3.2.25.3.1.2-target-pair-scoped-rfcomm-error-qualification-and-offline-salvage.md)
- [r25.3.1.3 exact observed frame grammar](r1.3.3.2.25.3.1.3-exact-adb-toggle-frame-grammar-and-field-role-closure.md)
- [`publication/`](publication/) for machine-readable contracts and flows

Repair-only `.1.x` releases remain part of the audit trail and are summarized by
the final supersession map.

## Next boundary

The next phase is independent confirmation and code/reply correlation. Repeat
the four-action stock capture on an independent session or build, correlate the
observed envelope and sequence candidate with constructors or native transforms,
and recover positive reply, authorization, integrity, session-binding, and
rollback semantics. Custom RFCOMM transmission and captured-payload replay remain
disabled.
