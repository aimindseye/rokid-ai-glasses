# Known Boundaries Before Live r25 Qualification

## Pairing control

Earlier static analysis recovered a real outbound native operation:

```text
endpoint:  CXRControl
operation: startBTPairing
argument:  one unsigned integer
```

This proves a control-plane boundary but not the underlying Bluetooth profile, session authentication, transport framing or glasses-side handler.

## Developer Mode

The exact glasses-side setting key is:

```text
settings_developer_mode
```

Known effects:

```text
enable:  persist.vendor.adb=true
         Settings.Global.adb_enabled=1

disable: persist.vendor.adb=false
```

The exact phone-side request, authenticated session, device addressing, reply and rollback contract remain unresolved.
