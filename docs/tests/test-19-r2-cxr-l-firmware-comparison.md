# Test 19 r2 — CXR-L Authorization and Firmware Comparison

This test replaces the withdrawn Test 19 r1 CXR-M ownership workflow. It keeps
Hi Rokid active and qualifies one CXR-L `CUSTOMAPP` session on YodaOS-Sprite
1.22, then repeats the same client after the offered 1.23 firmware update.

Canonical execution instructions are in the
[Test 19 r2 developer runbook](../developer/companion-app/test-19-r2-qualification.md).

## Acceptance boundary

- exact Hi Rokid `G1.11.11.0727`;
- exact CXR-L `client-l:1.0.1` artifact attestation;
- Hi Rokid authorization token received but never logged;
- `onCXRLConnected(true)` observed;
- `onGlassBtConnected(true)` observed;
- clean disconnect;
- stock Hi Rokid recovery;
- optional separate PCAPdroid metadata gate;
- no media, upload, reboot, unpair, or force-stop operations.

## r2.1 exact client-l 1.0.1 API-surface repair

The first physical preparation run proved that the published `client-l:1.0.1`
AAR does not contain `com.rokid.cxr.link.utils.GlassInfo`. The original r2
synthetic stubs incorrectly invented that class and three callback methods.
r2.1 removes the unsupported callbacks, attests the real four-method
`ICXRLinkCbk` surface, preserves a private class inventory and `javap` report,
and prevents resolver failures from being misreported as APK-install failures.
No glasses or Hi Rokid operation occurs during this repair.

## r2.2 preparation correction

The r2.1 resolver incorrectly searched only methods declared directly by
`CXRLink`. Exact artifact inspection showed that all four required connection
methods are inherited from `ExternalAppClient`. r2.2 attests the superclass,
method owners, exact descriptors, callback set, constructors, and immutable
artifact hashes before Gradle is allowed to run.


## r2.3 Gradle module-isolation and governed-install repair

A physical build probe proved that the CXR-L module compiles when Gradle is
given both `rokidCxrVersion=1.2.2` and `rokidCxrLVersion=1.0.1`, but the CXR-M
property was required only because the unrelated `test19` project threw during
configuration. r2.3 makes each SDK property task-scoped: a CXR-M task requires
only `rokidCxrVersion`, and a CXR-L task requires only `rokidCxrLVersion`.

The governed preparation command now invokes `:test19r2:clean` and
`:test19r2:assembleDebug` with only `-ProkidCxrLVersion=1.0.1`, preserves the
APK and build records under the private Maven evidence directory, installs the
APK, verifies package version `2.3.2-test19-r2.3.2`, optionally clears only this
test app's data, and removes generated build output after preservation. The
repository ignores `android-client/*/build/` as a defense-in-depth hygiene
rule. Hi Rokid data, Bluetooth pairing, and glasses firmware remain unchanged.


## r2.3.2 validated Gradle action and build-first resume

The r2.3.1 parameterized `Action<TaskExecutionGraph>` lambda still failed
Gradle Kotlin DSL compilation. A detached physical Gradle 8.13/Java 23 probe
validated the anonymous implementation used by r2.3.2 in both modules. The
probe proved that CXR-L builds with only `rokidCxrLVersion=1.0.1`, that a
selected CXR-M task fails without its own property, and that the same CXR-M
task passes when `rokidCxrVersion=1.2.2` is supplied.

r2.3.2 separates the workflow into an ADB-free build stage and a resumable
installation stage. Stage 1 resolves, attests, builds, verifies APK identity,
preserves immutable evidence, and cleans all generated output. Stage 2 accepts
only a successfully hashed Stage 1 evidence directory, repeats APK hash and
identity checks, verifies the exact Hi Rokid baseline, and then installs the
preserved APK. Stage 2 performs no Maven or Gradle operation. The governed APK
identity is `2.3.2-test19-r2.3.2`, version code 6.
