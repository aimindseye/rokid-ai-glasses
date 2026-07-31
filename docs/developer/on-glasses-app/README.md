# On-Glasses Application Track

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=planned; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Planned |
| Last reviewed | 2026-07-30 |


## Purpose

Determine how much functionality can be delivered by a normal or privileged APK
on stock firmware before considering firmware modification.

## Minimal qualification

1. Install a small signed APK over qualified USB ADB.
2. Start a screenless foreground service or explicit component.
3. Read non-sensitive system and hardware information.
4. Receive one explicit phone command through an approved interface.
5. Return one bounded response.
6. Survive the intended screenless lifecycle.
7. Uninstall and restore stock behavior cleanly.

## Permission boundary

Classify every required capability as:

- ordinary application permission;
- runtime permission;
- signature or privileged permission;
- Rokid service contract;
- SELinux blocked;
- root or firmware modification required.

## Decision rule

If an ordinary app or supported service exposes camera, audio, input, and
status, stay on stock firmware. If only a privileged app is required, prefer the
smallest system-app change. Escalate to firmware only after recovery and vendor
component preservation are proven.
