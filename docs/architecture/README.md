# Architecture Documentation

- [Root architecture summary](../../ARCHITECTURE.md)
- [Detailed non-display system architecture](non-display-system-architecture.md)
- [Current implementation status](../project-status.md)
- [Final RFCOMM connection-only closure](../research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md)
- [Machine-readable runtime status](../research/connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json)
- [Connection-protocol research](../research/connection-protocol/README.md)
- [Native-loader architecture](../research/native-loader/loader-architecture.md)
- [Protected-application evidence flow](../research/protected-application/publication/protected-application-evidence-flow.mmd)

The architecture now distinguishes a proven independent RFCOMM transport
foundation from the unresolved CXR/application framing and Developer Mode
command layer.
