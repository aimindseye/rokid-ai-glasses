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
