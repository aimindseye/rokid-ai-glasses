# Test 19 r2 — CXR-L Authorization and Firmware Comparison

This test replaces the withdrawn Test 19 r1 CXR-M ownership workflow. It keeps
Hi Rokid active and qualifies one CXR-L `CUSTOMAPP` session on YodaOS-Sprite
1.22, then repeats the same client after the offered 1.23 firmware update.

Canonical execution instructions are in the
[Test 19 r2 developer runbook](../developer/companion-app/test-19-r2-qualification.md).


## Final result

Both controlled connection runs passed. No CXR-L compatibility regression was
observed between firmware `1.22.009-20260710-151201` and
`1.23.009-20260725-153201` for Hi Rokid `G1.11.11.0727` and CXR-L
`client-l:1.0.1`. The event-type sequence and normalized behavioral signature
were the same in both runs.

The successful path was fallback-service-bind assisted in both cases:
`CXRLink.connect()` returned `false`, the exported CXR-L service bind started,
and both required callbacks arrived. Stock Hi Rokid recovery passed after SDK
disconnect.

- [Final findings](../developer/companion-app/test-19-r2-final-findings.md)
- [Machine-readable comparison](../research/connection-protocol/publication/test19-r2-cxr-l-firmware-comparison.json)
- [Public evidence hashes](../research/connection-protocol/publication/test19-r2-cxr-l-evidence-hashes.txt)

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
## r2.4 publication and runtime repairs

r2.4 publishes the sanitized firmware comparison and exact private-evidence
hashes without committing private ZIP bytes. It replaces the stale hardcoded
runtime app-version label with `PackageManager` identity and makes disconnect
cleanup state-aware. The repair APK is `2.4-test19-r2.4`, version code 7; the
accepted firmware comparison remains the r2.3.2 APK run and is not rewritten.


## r2.4.1 physical smoke closure

The r2.4 repair APK was built with package
`org.aimindseye.rokid.cxrlqualification`, version code `7`, version name
`2.4-test19-r2.4`, and SHA-256
`c72f72303d1f29c08ae9faab94bb6fde54ff8a3ab31fc56664eff84c5c174e25`.
A bounded smoke run on firmware `1.23.009-20260725-153201` passed the same
connection and stock-recovery gates. The runtime event identity was sourced
from `PackageManager`, and cleanup recorded
`SKIPPED_SDK_DISCONNECT_SUCCEEDED` with no manual-unbind attempt or error.

The private smoke ZIP SHA-256 is
`35e75e6e98933436e7799cfceb8a47e71e31d95ac17b73c1a87516de1257593e`.
The private ZIP is not committed. This closure changes publication status only;
it does not change runtime code or replace the accepted firmware-comparison
runs.
