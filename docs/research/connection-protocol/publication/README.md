# Connection-Protocol Publications

Machine-readable files in this directory describe accepted sanitized research
boundaries. Private evidence bytes, credentials, authorization-token values,
device serials, raw Bluetooth addresses, and media payloads are excluded.

## Test 19 r2.4.1 CXR-L publication closure

- [Firmware comparison JSON](test19-r2-cxr-l-firmware-comparison.json)
- [Public evidence hashes](test19-r2-cxr-l-evidence-hashes.txt)
- [Developer-facing final findings](../../../developer/companion-app/test-19-r2-final-findings.md)

The publication records the accepted firmware comparison and the r2.4
repair-only physical smoke closure.

## Test 20 r1.2 final corrected capability census

- [Machine-readable corrected census](test20-r1-cxr-l-capability-census.json)
- [Human-readable corrected census](test20-r1-cxr-l-capability-census.md)
- [Evidence identities](test20-r1-cxr-l-evidence-hashes.txt)
- [Publication schema](test20-r1-cxr-l-capability-census.schema.json)
- [Final publication closure](../../../tests/test-20-r1-2-cxr-l-final-publication.md)

Test 20 r1.2 publishes the reviewed r1.1 repair. Runtime qualification is
restricted to nine descriptor-exact members and two Hi Rokid components. The
first r1 sanitized output remains withdrawn because it propagated class-level
participation to unrelated members.

The corrected census is a selection boundary, not permission to invoke every
listed surface. Camera, audio, AI-assist callbacks, custom commands, custom
views, glass-app operations, provider access, and native/JNI behavior remain
untested.
