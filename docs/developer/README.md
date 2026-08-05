# Developer Guide

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=mixed; last_reviewed=2026-07-31 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Mixed |
| Last reviewed | 2026-07-31 |


This section turns the validated research foundation into an implementation
roadmap for three goals:

1. a custom Android companion app that can replace Hi Rokid where qualified;
2. on-glasses software and, only where necessary, custom firmware;
3. a reusable device–hub–brain platform for multiple smart-glasses families.

## Start here

- [Current capability status](current-status.md)
- [Development roadmap](roadmap.md)
- [Device architecture](device-architecture.md)
- [SDK and CXR qualification](sdk-and-cxr/README.md)

## Implementation tracks

- [Companion application](companion-app/README.md)
  - [Requirements](companion-app/requirements.md)
  - [Qualification test plan](companion-app/test-plan.md)
  - [Test 22 networking boundary](companion-app/test22-networking-boundary.md)
  - [Test 19 r2: Hi Rokid CXR-L firmware comparison](companion-app/test-19-r2-qualification.md)
  - [Withdrawn Test 19 r1 CXR-M experiment](companion-app/test-19-r1-qualification.md)
  - [Lifecycle and recovery](companion-app/lifecycle.md)
- [On-glasses application](on-glasses-app/README.md)
- [Bluetooth and media](bluetooth-and-media/README.md)
- [ADB and Developer Mode](adb-and-developer-mode/README.md)
- [Firmware research](firmware/README.md)
- [Common SmartGlasses platform](platform/README.md)
  - [Device–hub–brain architecture](platform/device-hub-brain-architecture.md)
  - [Cross-device abstraction](platform/cross-device-abstraction.md)
  - [Security and privacy](platform/security-and-privacy.md)

## Evidence and reproduction

- [Research library](../research/README.md)
- [Current project status](../project-status.md)
- [Public scripts](../../scripts/README.md)
- [Shared reference](../reference/README.md)

- [Test 19 r2 final findings](companion-app/test-19-r2-final-findings.md)
