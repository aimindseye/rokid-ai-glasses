# Protected Loader Runtime Findings — Current Synthesis

This document supplements, but does not replace, the accepted historical
native-runtime closure in [`r1.3.3.2.22.1.1-findings.md`](r1.3.3.2.22.1.1-findings.md).

## Historical closure retained

The earlier evidence established the secondary runtime image, 68 external
relocation slots, 29 initializer executions, two finalizer targets with no
observed execution, exact attribution of 11 MyJni methods, `MyJni.cl` entry and
return, `MyJni.load` entry, wrapper `MyApplication` class loading, and
`Application.attach` entry. Those findings remain authoritative for that
capture and evidence schema.

## Later startup-materialization capture

A separate reviewed capture produced 647 structured events across two
protected-process sessions. It captured all 11 expected MyJni name/signature
pairs, 148 native DEX-source-open events, 12 hashed material candidates, 20,564
loaded classes, and 9 class loaders.

`MyJni.load` entered from the wrapper application's `attachBaseContext` path.
`MyJni.cl` executed and returned. The remaining nine registered methods were
not observed during the bounded startup window.

## Injection trigger boundary

Baseline and Frida spawn/resume without an agent survived. A zero-hook agent
that installed no Java bridge and no Interceptor hooks reached script load and
agent messaging in both tested injection modes, after which the injected target
terminated.

This proves that agent injection was sufficient in the reviewed experiments.
It does not establish the exact checked artifact or the internal exit primitive.

## Injection-mode comparison

| Observation | Early zero-hook injection | Attach to running target |
|---|---:|---:|
| Injection elapsed in detailed source run | 1113 ms | 3650 ms |
| Identity samples | 3 | 5 |
| Maps samples | 2 | 3 |
| Explicit burst death transition | 1 | 0 |
| Final live qualification | PASS with bounded death-race warning | PASS |
| Injected target alive at end | No | No |

The bounded `POST_INJECTION_DEATH_RACE` classification applies only after valid
pre-injection process/package lineage, complete injection reachability, valid
burst evidence, and later confirmed target death.

## Detection-surface evidence

The reviewed `libnesec.so` contains static references to `/proc/self/maps`,
`dl_iterate_phdr`, `dladdr`, `dlopen`, `dlsym`, `readlink`, `abort`, and
`raise`. These are bounded candidate surfaces, not proof of an executed branch.

A prior recovered high-frequency trial captured nine
`/memfd:frida-agent-64.so (deleted)` map lines in an early-injection transition
sample. The accepted standalone run did not repeat the map-name hit, so mapping
visibility is treated as timing-sensitive.

## Lifecycle boundary

Static DEX analysis identifies `com.rokid.sprite.global.RealApplication` as a
bounded protected-application candidate. Runtime completion through that real
application's startup lifecycle remains unresolved.
