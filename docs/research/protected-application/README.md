# Protected Application Evidence Review

This directory publishes the accepted r24 and r24.1 analysis that followed the
[native-loader research](../native-loader/README.md).

## Accepted r24.1 result

- `RealApplication` status:
  `STATIC_CANDIDATE_NOT_PRESENT_IN_RUNTIME_CLASS_INVENTORY`; runtime confirmation
  remains **false**.
- Six APK artifacts were scanned without reported parser errors.
- Nine wrapper focus classes gained exact file-backed APK DEX attribution.
- Seven of 11 MyJni methods have exact DEX invoke sites.
- 24 physical invoke observations reduce to eight unique logical sites across
  two wrapper classes.
- `cl` and `load` remain runtime-confirmed startup methods.
- `cp`, `ip`, `ra`, `rp`, and `run` are static-caller-only startup-path
  candidates.
- `d`, `e`, `ed`, and `getEnvInfo` remain caller-unresolved.
- No user-facing business-feature meaning is proven for any abbreviated method.

## Read in this order

1. [RealApplication lifecycle](real-application-lifecycle.md)
2. [Class-origin differential](class-origin-attribution.md)
3. [Exact MyJni caller map](myjni-caller-map.md)
4. [Caller-to-feature correlation](caller-feature-correlation.md)
5. [Methodology](methodology.md)
6. [Limitations](limitations.md)
7. [Evidence hashes](evidence-hashes.txt)
8. [Runtime status](runtime-status-summary.json)
9. [Machine-readable publication](publication/README.md)

## Engineering implication

The caller census improves startup-path attribution, but it does not expose the
stock phone-to-glasses command protocol. It does not yet enable an independent
companion app or Developer Mode toggle. See [project status](../../project-status.md).
