# Protected Application Evidence Review

This directory publishes the accepted r24.1 comparison between the bounded runtime-only analysis and the six-APK enhanced analysis.

## Accepted result

- RealApplication: `STATIC_CANDIDATE_NOT_PRESENT_IN_RUNTIME_CLASS_INVENTORY`; runtime confirmation remains **false**.
- Six APK artifacts were scanned without reported parser errors.
- Nine wrapper focus classes gained exact file-backed APK DEX attribution.
- Seven of 11 MyJni methods have exact DEX invoke sites.
- 24 physical invoke observations reduce to eight unique logical call sites across two wrapper classes.
- `cl` and `load` remain runtime-confirmed startup methods.
- `cp`, `ip`, `ra`, `rp`, and `run` are static-caller-only startup-path candidates.
- `d`, `e`, `ed`, and `getEnvInfo` remain caller-unresolved.
- No user-facing business-feature meaning is proven for any abbreviated method.

See [`publication/accepted-evidence-review.json`](publication/accepted-evidence-review.json) for the machine-readable review.
