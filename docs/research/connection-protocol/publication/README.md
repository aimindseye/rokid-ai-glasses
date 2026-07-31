# r25 Bootstrap Publication

Machine-readable files in this directory describe the known starting boundary and the client safety contract. Live capture results should be published only after private evidence review and sanitization.

## Test 19 r2.4.1 CXR-L publication closure

- [Firmware comparison JSON](test19-r2-cxr-l-firmware-comparison.json)
- [Public evidence hashes](test19-r2-cxr-l-evidence-hashes.txt)
- [Developer-facing final findings](../../../developer/companion-app/test-19-r2-final-findings.md)

The publication records the accepted firmware comparison plus the r2.4
repair-only physical smoke closure. Only sanitized outcomes and hashes are
published. Private evidence ZIP bytes, authorization-token values, phone
serials, raw Bluetooth addresses, and media payloads are excluded.

## Test 20 r1 capability-census tooling

- [Execution and interpretation guide](../../../tests/test-20-r1-cxr-l-capability-census.md)
- [Sanitized publication schema](test20-r1-cxr-l-capability-census.schema.json)

Test 20 r1 resolves and verifies the exact CXR-L 1.0.1 artifact, inventories
its public Java and native/JNI surfaces, compares the exported Hi Rokid CXR-L
components, and generates a sanitized publication outside the repository. No
Test 20 result is promoted here until the generated publication is reviewed in
a separate publication-only closure.
