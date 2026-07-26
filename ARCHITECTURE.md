# Rokid AI Glasses Style Architecture

This is the short architecture entry point. The detailed, evidence-labeled
architecture is maintained in
[`docs/architecture/non-display-system-architecture.md`](docs/architecture/non-display-system-architecture.md).

## System layers

```mermaid
flowchart LR
    U[Wearer] --> G[Glasses hardware]
    G --> GO[Glasses Android 12 and Rokid services]
    GO <--> T[Bluetooth media/control transport]
    T <--> P[Hi Rokid Android app]
    P <--> C[Rokid account, AI, object storage and OTA services]
    P --> L[Phone-local cache and settings]

    P --> W[Protected wrapper and libnesec loader]
    W --> J[MyJni and wrapper class-loader handoff]
    J -. complete protected application unresolved .-> R[RealApplication candidate]
```

## Proven boundaries

- The glasses are a complete Android device with privileged Rokid services.
- The phone is the observed cloud gateway for the tested voice and visual AI
  paths.
- Hi Rokid handles binding, model selection, AI WebSockets, visual uploads,
  firmware checks, background services, and retained conversation state.
- The protected wrapper/native-loader boundary and exact 11-method `MyJni`
  registration contract are documented.
- The r24.1 review recovered eight logical DEX call sites for seven `MyJni`
  methods but did not prove business-feature semantics.

## Unresolved implementation boundary

The repository does not yet contain an independent Android companion that can
bind, authenticate, establish the stock command channel, read glasses state, or
change Developer Mode. The glasses-side Developer Mode property changes are
known statically; the remote invocation path is not.

See:

- [Current project status](docs/project-status.md)
- [Detailed architecture](docs/architecture/non-display-system-architecture.md)
- [Test and research matrix](docs/tests/test-matrix.md)
- [Protected-application review](docs/research/protected-application/README.md)
