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
| CXR/application framing and request/reply correlation | Unresolved |
| Stock ADB enable/disable command | Unresolved |
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
- [`publication/`](publication/) for machine-readable contracts and flows

Repair-only `.1.x` releases remain part of the audit trail and are summarized by
the final supersession map.

## Next boundary

The next phase is stock ADB-toggle payload capture and application-framing
recovery. No custom application payload should be transmitted until a decoder
explains independent enable and disable captures and request/reply correlation.
