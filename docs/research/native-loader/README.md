
# Hi Rokid Protected Native Loader Research

This directory publishes the sanitized, evidence-bounded findings from a
combined static and runtime investigation of the global **Hi Rokid** Android
application:

```text
com.rokid.sprite.global.aiapp
```

The public title describes the technical subject. Internal release identifiers
are retained only where needed for reproducible provenance.

## Headline result

Observed runtime evidence supports this startup sequence:

```text
libnesec.so protected loader
  → secondary runtime image materialization
  → runtime relocation resolution
  → initializer callback execution
  → dynamic RegisterNatives
  → MyJni.cl / MyJni.load handoff
  → MyApplication class loading
  → Application.attach entry
```

Six previously declared runtime blockers were closed. The strongest exact
results are:

- 68 external relocation slots captured;
- 29 initializer targets executed;
- two finalizer targets identified but not observed executing;
- 14 registered methods across three classes;
- exactly 11 methods attributed to `com.netease.nis.wrapper.MyJni`;
- `MyJni.cl` entered and returned;
- `MyJni.load` entered before the observed process exit;
- `com.netease.nis.wrapper.MyApplication` loaded twice;
- `Application.attach` entry observed.

## Read in this order

1. [Validated findings](r1.3.3.2.22.1.1-findings.md)
2. [Loader architecture](loader-architecture.md)
3. [Dynamically registered JNI map](jni-registration-map.md)
4. [Six-blocker closure](six-blocker-closure.md)
5. [Runtime event types](runtime-event-types.md)
6. [Methodology](methodology.md)
7. [Limitations](limitations.md)
8. [Evidence hashes](evidence-hashes.txt)
9. [Machine-readable status summary](runtime-status-summary.json)

The raw Mermaid source for the main diagram is in
[`loader-control-flow.mmd`](loader-control-flow.mmd).

## Evidence labels

- **Observed** — directly captured or reproduced.
- **Inferred** — best-supported interpretation from observed evidence.
- **Unresolved** — not established by the bounded evidence.

## Public/private boundary

This directory does **not** contain:

- APKs or native libraries;
- transformed or relocated binary snapshots;
- recovered proprietary DEX files;
- memory dumps or absolute runtime-address maps;
- raw Frida events, logcat, tombstones or process maps;
- account data, tokens, serials, Bluetooth addresses or precise location;
- decrypted packet captures or SSL key logs.

Private evidence remains outside the Git worktree. Public provenance is
represented through hashes, counts, sanitized status records, diagrams and
original generic tooling.
