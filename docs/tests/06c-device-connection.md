# Test 06c — Device Connection and Optional Bluetooth Peripherals

## Status

**Complete — valid empty-discovery control.**

The investigation is closed without purchasing a compatible ring or controller.

## Scope

The Hi Rokid Android application exposes a **Device connection** setting described as:

> Connect Bluetooth peripherals such as rings or control panels for interaction with the glasses.

The test asked:

1. whether the phone performs an identifiable Rokid-specific BLE scan;
2. whether a compatible peripheral can be discovered without a reference device;
3. whether the feature is mediated through the connected glasses;
4. whether the application contains a native command boundary for peripheral pairing.

## Tested configuration

- Hi Rokid Android application: `G1.10.11.0713`
- Version code: `10100011`
- Display-free Rokid AI Glasses connected to the phone
- No compatible ring or control panel present
- No peripheral selected or paired

Device addresses, account identifiers, raw logcat, APKs, decompiled application trees, and native binaries remain private.

## Dynamic result

The Device connection screen displayed zero compatible peripherals.

The captured Android Bluetooth diagnostics did not reveal a phone-side Rokid-specific filter using:

- a device-name pattern;
- a primary service UUID;
- a solicitation UUID;
- a manufacturer identifier.

Service-data scans involving `FE2C`, `FEAA`, and `FFF6` were present, but they were background/platform activity and are not treated as evidence of a Rokid ring protocol.

An earlier Companion Device Manager association filter using `0x9100` belonged to initial glasses association/presence handling. It is not identified as an optional-ring service.

The phone continued exchanging vendor commands with the already connected glasses through a Bluetooth Classic RFCOMM path. A log label containing `WordTips_AllDevices` was observed, but its exact command semantics were not established.

## Static result

The application resources contain dedicated Device connection strings, including:

- `prompter_settings_connect_device`
- `prompter_settings_connect_device_desc`
- `prompter_settings_connect_device_dis`

The application manifest registers a `ConnectCompanionDeviceService`. That service supports the existing phone/glasses association architecture, but registration alone does not prove that Android performs optional-peripheral discovery.

The native library `libcxr-bridge-jni.so` exposes:

```text
NativeCXRBridge::startBTPairing(unsigned int)
```

The function constructs a nested `rokid::Caps` message:

```text
outer:
  unsigned integer 0
  inner Caps:
    string "startBTPairing"
    unsigned integer argument
```

It then passes the outer Caps value and a short string decoded as `CXRControl` to a virtual method on the bridge-held transport object.

The function does not call Android BLE scanner, GATT, Companion Device Manager, or Bluetooth pairing APIs.

## Conclusion

The evidence strongly supports this control path:

```text
Hi Rokid Device connection UI
        ↓
NativeCXRBridge::startBTPairing(value)
        ↓
Rokid Caps command: "startBTPairing"
        ↓
CXRControl transport endpoint
        ↓
connected glasses control plane
```

The connected glasses are therefore the likely component that performs or manages compatible-peripheral discovery and pairing.

This remains a bounded conclusion: the receiving glasses-firmware implementation was not inspected, and no compatible peripheral was available for end-to-end confirmation.

## Unresolved

The investigation did not establish:

- which ring or controller models are accepted;
- whether `RGR06` is accepted;
- the meaning of the unsigned integer argument;
- advertisement name or manufacturer data;
- service and characteristic UUIDs;
- bonding or authentication behavior;
- GATT command/event encoding;
- whether any phone-side component participates after a glasses-side discovery result.

## Closure decision

Further protocol identification requires a genuine compatible peripheral or an independently captured advertisement/GATT profile. Because no compatible device is available and none will be purchased for this effort, 06c is closed at the confirmed control-command boundary.
