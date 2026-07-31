# Developer Current Status

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Replacement companion boundary

| Capability | Current status |
|---|---|
| Stock pairing and binding behavior | Observed |
| Runtime RFCOMM endpoint attribution | Complete in accepted r25.2 scope |
| Independent RFCOMM open/close | Device-qualified |
| Channel identity | SCN 3, DLCI 6, MTU 990 |
| Application bytes in accepted connection-only attempt | Proven zero in both directions |
| Stock ADB-toggle outbound message family | Four qualified messages attributed and decoded |
| Reply, authorization, integrity, and session binding | Unresolved |
| Independent Developer Mode sender | Not implemented; replay prohibited |
| Style-qualified CXR-M client | Test 19 harness implemented; physical qualification pending |
| Independent camera capture | Not yet tested |
| Independent microphone and speaker path | Not yet tested |
| Complete Hi Rokid replacement | Not built |

## On-glasses and firmware boundary

| Capability | Current status |
|---|---|
| Android/API identity | Android 12/API 32 observed |
| USB ADB | RSA-protected transport qualified while Developer Mode enabled |
| Ordinary APK lifecycle on Style | Not yet qualified |
| Privileged permission boundary | Not yet mapped |
| Live/OTA vbmeta correspondence | Read-only match established for the qualified chain |
| Repaired Magisk candidate | Accepted offline only; never booted or flashed |
| Proven recovery path for custom firmware | Not established |

## Recommended next gate

The immediate next engineering gate is
[Test 19 r1: Maven-resolved CXR-M qualification](companion-app/test-19-r1-qualification.md).
Custom firmware is not the critical path unless supported APIs and an ordinary
on-glasses application cannot provide the required camera, microphone, speaker,
input, and offline-control capabilities.

## Evidence

- [Project status](../project-status.md)
- [Connection-protocol research](../research/connection-protocol/README.md)
- [Boot-chain research](../research/boot-chain/README.md)
