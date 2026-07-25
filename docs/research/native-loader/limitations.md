
# Limitations and Unresolved Questions

## Lifecycle completion

Observed:

- `MyApplication` class loading;
- `Application.attach` entry.

Not observed:

- `Application.attach` return;
- `LoadedApk.makeApplication` execution;
- `Instrumentation.callApplicationOnCreate` execution.

The public finding is therefore **protected Java handoff**, not complete
application startup.

## Protected application recovery

The evidence does not contain or establish:

- a complete protected DEX/class inventory;
- the complete protected application implementation;
- a reconstructed first-party APK;
- business-protocol or backend compatibility;
- authentication or device-binding bypass.

## Native-method semantics

Eleven MyJni names and signatures are proven. Only `cl` completion and `load`
entry were observed. Names such as `d`, `e`, `cp`, `ip`, `ra`, `rp` and `ed`
are not assigned speculative meanings.

## Callback lifecycle

All 29 initializer callbacks executed during the captured startup. Two
finalizer targets were present but no finalizer execution was observed. This
does not prove the finalizers are unreachable.

## Post-transform snapshot

The snapshot is represented publicly by size and SHA-256 only. It is not
published, and its captured state was not a standalone ordinary ELF file at
the sampled boundary.

## Process exit

Android reported `EXIT_SELF`, status 28, without a tombstone, and the
application later relaunched. The reason for status 28 is unresolved. The
public report does not classify it as a crash or anti-instrumentation mechanism.

## Product and version scope

Findings apply to the tested global Hi Rokid package and arm64 runtime. They
must not be generalized automatically to China-region builds, display-equipped
Rokid products, future app versions, iOS, or other smart-glasses vendors.
