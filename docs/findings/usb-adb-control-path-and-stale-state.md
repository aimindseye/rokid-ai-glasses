# USB ADB control path and stale-state hypothesis

## Finding

Static analysis of the exact stock software identifies the Developer Mode
setting key and glasses-side property writes:

```text
settings_developer_mode=on
    → persist.vendor.adb=true
    → Settings.Global.adb_enabled=1

settings_developer_mode=off
    → persist.vendor.adb=false
```

No matching `Settings.Global.adb_enabled=0` write was recovered in the
available disable method.

## What this explains

The implementation can produce disagreement between a phone/framework
indicator and the vendor property that participates in ADB enablement:

```text
visible or framework state: enabled
persist.vendor.adb:         false
```

This is a credible explanation for an enabled-looking Developer Mode control
while the host sees no USB device. It is one hypothesis, not a live reading of
the current glasses state.

## Privilege boundary

The relevant Rokid packages statically resolve to `priv_app`.
`persist.vendor.adb` maps to `adbd_config_prop`.

The reviewed text-policy sources did not close whether `priv_app` is directly
authorized after all compiled-policy attributes are expanded. They also did
not prove a denial.

A normal user-installed glasses APK should not be assumed capable of directly
setting the vendor property or secure global ADB state.

## Cable boundary

The exact firmware analysis found generic charger-side debug-board detection,
but no direct connection to ADB or an official cable identifier.

This means neither side of the diagnosis is closed:

- a supported data/debug cable, contact, or signal issue remains possible;
- a stale property or USB-gadget-state failure remains possible.

The cable model's successful use by other owners is useful field evidence
against universal incompatibility, but it does not qualify the individual
cable, connector seating, adapters, or the tested unit.

## Repair-app direction

The strongest practical software candidate is a phone-side client that
replays the normal authenticated setting transaction:

```text
off → acknowledged → on → acknowledged
```

It is not yet implementation-ready. The remaining blockers are the CXR wire
envelope, authentication/session setup, addressing, correlation, and reply
semantics.

## Safety boundary

The current investigation authorizes no blind recovery navigation, sideload,
fastboot operation, flashing, verified-boot modification, or slot change.
