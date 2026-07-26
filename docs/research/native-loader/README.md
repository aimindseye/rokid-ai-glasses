# Hi Rokid Protected Native Loader Research

This directory publishes the sanitized, evidence-bounded native-loader and
startup-trigger findings for the global Hi Rokid Android package:

```text
com.rokid.sprite.global.aiapp
```

## Evidence sets

The directory intentionally preserves two related but distinct public evidence
sets.

### Historical native-runtime and Java-handoff closure

- [Validated r22 findings](r1.3.3.2.22.1.1-findings.md)
- [Historical loader architecture](loader-architecture.md)
- [Original loader-flow diagram](loader-control-flow.mmd)
- [Exact JNI registration map](jni-registration-map.md)
- [Original six-blocker closure](six-blocker-closure.md)
- [Original 102-event inventory](runtime-event-types.md)
- [Legacy runtime status](runtime-status-summary.json)

This evidence established the secondary runtime mapping, 68 external
relocations, 29 initializer executions, 11 exact MyJni registrations,
`MyJni.cl` completion, `MyJni.load` entry, wrapper class loading, and
`Application.attach` entry.

### Later startup-materialization and injection-trigger publication

- [Current synthesis](protected-loader-runtime-findings.md)
- [Injection-mode comparison](injection-mode-comparison.md)
- [Trigger-status summary](runtime-trigger-status-summary.json)
- [Machine-readable publication](publication/README.md)
- [Generic observation-only Frida templates](../../../tools/frida/README.md)

The later capture recorded 148 native DEX-source-open events, 12 hashed material
candidates, 20,564 loaded classes, and 9 class loaders. Baseline and spawn/resume
without an agent survived; zero-hook agent loading was followed by target death
in both tested injection modes. The exact detection predicate and exit primitive
remain unresolved.

## Next research layer

The r24/r24.1 APK-enhanced class-origin and caller analysis is published in the
[protected-application directory](../protected-application/README.md).

## Public/private boundary

No APKs, native libraries, transformed snapshots, recovered proprietary DEX,
memory dumps, raw Frida events, process maps, tokens, device identifiers, or
absolute runtime addresses are published here. See [methodology](methodology.md),
[limitations](limitations.md), and [evidence hashes](evidence-hashes.txt).
