# Stock Connection Protocol and Minimal Companion Research

This directory begins the implementation-focused phase after Tests 00–18 and protected-companion research through r24.1.

## Current state

| Boundary | Status |
|---|---|
| Stock `CXRControl/startBTPairing` operation | Proven statically |
| Glasses-side Developer Mode key and property effects | Proven statically |
| Bluetooth service/channel identity | Pending r25 live capture |
| Pairing/binding authentication | Unresolved |
| Message framing and request/reply correlation | Unresolved |
| Read-only Android Bluetooth probe | Implemented in `android-client/` |
| Independent stock CXR session | Not implemented |
| Independent Developer Mode toggle | Disabled and not implemented |

## Read next

- [Known boundaries](known-boundaries.md)
- [Capture methodology](capture-methodology.md)
- [Developer Mode attribution](developer-mode-attribution.md)
- [Minimal client status](minimal-client-status.md)
- [`publication/`](publication/) for machine-readable bootstrap contracts
<!-- BEGIN R1.3.3.2.25.1 CONNECTION PROTOCOL STATUS -->
## r25.1 closure

The accepted stock capture closes BLE characteristic `0x9301` → runtime UUID → SDP SCN 3 → RFCOMM DLCI 6/MTU 990. Read [the detailed findings](r1.3.3.2.25.1-findings.md) and the [sanitized machine-readable status](publication/r25.1-stock-session-closure.json). Application framing and Developer Mode invocation remain open.
<!-- END R1.3.3.2.25.1 CONNECTION PROTOCOL STATUS -->

## r1.3.3.2.25.2

- [Findings](r1.3.3.2.25.2-findings.md)
- [Implementation contract](publication/r25.2-connection-only-client.json)
- [Flow](publication/r25.2-connection-only-flow.mmd)

## r1.3.3.2.25.2.1

- [Power-state differential BLE attribution findings](r1.3.3.2.25.2.1-findings.md)
- [Capture contract](publication/r25.2.1-attribution-contract.json)
- [Capture flow](publication/r25.2.1-attribution-flow.mmd)

This release is capture-only. It repairs scan lifecycle handling and clusters
advertisement fingerprints across glasses-off, power-on-transition, and
steady-on phases. It does not attempt GATT, RFCOMM, or application payload I/O.


## r1.3.3.2.25.2.2 — stock-assisted BLE endpoint attribution

This bounded phase uses Hi Rokid as an attribution oracle for one controlled reconnect. A scan-only companion records per-run HMAC address tokens and advertisement fingerprints. The host captures stock-app and Bluetooth-system logs, attributes the unique provisioning-GATT address associated with the `0x9301` read, computes the same HMAC token, and produces a private endpoint-handoff record plus a sanitized publication result. No independent GATT or RFCOMM connection is attempted.

<!-- BEGIN R1.3.3.2.25.2.4 FINAL RFCOMM CLOSURE -->
## Current RFCOMM connection-only conclusion

The authoritative result is **full Android client RFCOMM zero-payload runtime closure**, proven by the strict private-handoff `.3.2` run and a lossless HCI DLCI-frame census.

- Final publication: [`r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md`](r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md)
- Runtime status: [`r1.3.3.2.25.2.4-runtime-status-summary.json`](r1.3.3.2.25.2.4-runtime-status-summary.json)
- Evidence identities: [`r1.3.3.2.25.2.4-evidence-hashes.txt`](r1.3.3.2.25.2.4-evidence-hashes.txt)
- Supersession map: [`r1.3.3.2.25.2.4-supersession-map.json`](r1.3.3.2.25.2.4-supersession-map.json)

Accepted invariants: SCN `3`, DLCI `6`, MTU `990`; TX payload `0` bytes; RX payload `0` bytes. Earlier bounded results remain historical evidence but are superseded for the final zero-payload qualification.
<!-- END R1.3.3.2.25.2.4 FINAL RFCOMM CLOSURE -->
