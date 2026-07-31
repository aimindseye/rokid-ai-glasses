# Test 19 r2.4.1 — Final CXR-L Firmware Comparison Closure

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=validated; last_reviewed=2026-07-31 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Validated |
| Last reviewed | 2026-07-31 |

## Final result

No CXR-L compatibility regression was observed between firmware
`1.22.009-20260710-151201` and `1.23.009-20260725-153201` for the tested stack. Both controlled
runs authorized through Hi Rokid, configured a `CUSTOMAPP` session, received
`onCXRLConnected(true)` and `onGlassBtConnected(true)`, disconnected through
the SDK, and returned to a working stock Hi Rokid session.

| Check | Firmware 1.22 | Firmware 1.23 |
|---|---|---|
| Qualification | `CXR_L_CONNECTION_AND_STOCK_RECOVERY_PASS` | `CXR_L_CONNECTION_AND_STOCK_RECOVERY_PASS` |
| Event count | `15` | `15` |
| SDK `connect()` return | `false` | `false` |
| Fallback service bind | `true` | `true` |
| CXR-L callback | `true` | `true` |
| Glasses Bluetooth callback | `true` | `true` |
| SDK disconnect | `true` | `true` |
| Hi Rokid recovery | `true` | `true` |

## Connection-path finding

In both runs, `CXRLink.connect()` returned `false`. The client then bound the
exported CXR-L media service using the SDK-owned `ServiceConnection`. Both
required callbacks arrived and the qualification completed. The accepted
classification is therefore **fallback-service-bind assisted**, not a claim
that the direct SDK call alone completed the connection.

## Runtime repairs in r2.4

The accepted r2.3.2 event files contain a stale hardcoded runtime label
`2.2-test19-r2.2` even though the
governed APK identity was `2.3.2-test19-r2.3.2`.
r2.4 reads version name and version code from Android `PackageManager` at
runtime instead of embedding a string in the event logger.

Both accepted runs also show `java.lang.IllegalArgumentException` when the app
attempted a redundant manual unbind after `CXRLink.disconnect()` succeeded.
r2.4 treats successful SDK disconnect as cleanup ownership, skips that manual
unbind, attempts manual unbind only after SDK disconnect failure, and suppresses
duplicate disconnect calls.

These repairs do not rewrite or reinterpret the accepted private evidence.

## r2.4.1 physical smoke closure

A bounded repair-only smoke run was completed on firmware
`1.23.009-20260725-153201` with the r2.4 APK. It repeated the accepted
authorization and fallback-assisted connection path, preserved stock Hi Rokid
recovery, and physically validated both runtime repairs:

- runtime identity came from `PackageManager` as version
  `2.4-test19-r2.4`, version code `7`;
- SDK disconnect returned successfully;
- manual unbind was not attempted;
- the disposition was `SKIPPED_SDK_DISCONNECT_SUCCEEDED`;
- no manual-unbind error class was recorded.

The smoke run passed all Test 19 r2 qualification markers. Firmware 1.22 was
not restored or rerun because the smoke scope was limited to validating the
r2.4 runtime repairs, not repeating the already accepted firmware comparison.

## Evidence identities

- Firmware 1.22 private ZIP SHA-256: `ffdf8a254bb25a7714a4759ae16b2ccf985c341329504d7590a8d47163be5385`
- Firmware 1.22 screenshot SHA-256: `a0cf4590e398b86978b21f85737d6330102724bfe6f0603566d840ee46320e2d`
- Firmware 1.23 private ZIP SHA-256: `a684c51ce794365f848aff448865a4653a6678859c47f308d733b0af00e8e8fc`
- Firmware 1.23 screenshot SHA-256: `919a5970e4d6216277563b809437ecda46b00d54f060f90485055dff753c3315`
- Governed r2.3.2 APK SHA-256: `8d34e9332bc2ab730d9c5a802f9efcb4ec4a940453470f260539ef9370665aa2`
- Governed r2.4 APK SHA-256: `c72f72303d1f29c08ae9faab94bb6fde54ff8a3ab31fc56664eff84c5c174e25`
- r2.4 runtime-smoke private ZIP SHA-256: `35e75e6e98933436e7799cfceb8a47e71e31d95ac17b73c1a87516de1257593e`

Private ZIP bytes, authorization-token values, phone serials, raw Bluetooth
addresses, and media payloads are not committed.

## Boundaries

- one accepted firmware-comparison connection run per firmware;
- one repair-only r2.4 smoke run on firmware 1.23;
- exact Hi Rokid `G1.11.11.0727` and CXR-L `client-l:1.0.1`;
- no media, AI, upload, reboot-recovery, or independent-Hi-Rokid qualification;
- no performance conclusion from operator-driven timing.
