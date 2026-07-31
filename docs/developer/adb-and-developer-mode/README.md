# ADB and Developer Mode

<!-- wiki-status: audience=developer; applies_to=rokid-ai-glasses-style-non-display; evidence=observed; last_reviewed=2026-07-30 -->

## Page status

| Field | Value |
|---|---|
| Audience | Developer |
| Applies to | Rokid AI Glasses Style (non-display) |
| Evidence status | Observed |
| Last reviewed | 2026-07-30 |


## Qualified facts

- the tested Style unit reported Android 12/API 32;
- USB ADB required RSA authorization;
- the original data/debug cable exposed the qualified transport;
- wireless ADB was disabled in the tested state;
- the build remained a production `user/release-keys` build;
- disconnecting the physical cable removed the observed ADB transport.

## Recovered stock semantics

The glasses-side setting key and bounded property writes include:

```text
settings_developer_mode = on | off

enable:
  persist.vendor.adb=true
  Settings.Global.adb_enabled=1

disable:
  persist.vendor.adb=false
```

No matching bounded `Settings.Global.adb_enabled=0` write was recovered in the
disable method. Existing ADB transport can remain after a stock disable action,
so transport disappearance is not a valid required oracle.

## Current restriction

The repository does not contain an independent Developer Mode sender. Captured
payload replay remains prohibited until reply, authorization, integrity,
session, failure, and rollback contracts are proven.

## Evidence

- [USB ADB finding](../../findings/glasses-android-os-and-adb.md)
- [Stock ADB-toggle findings](../../research/connection-protocol/stock-adb-toggle/findings.md)
