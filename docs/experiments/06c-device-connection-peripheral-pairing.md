# 06c — Optional Peripheral Pairing Control Path

## Research question

Does Hi Rokid scan directly from Android for an optional Bluetooth ring/controller, or does it ask the connected glasses to manage pairing?

## Evidence classes

The conclusion combines three evidence classes:

1. a controlled empty-discovery run;
2. Android Bluetooth and Companion Device Manager diagnostics;
3. static inspection of application resources and the native CXR bridge.

No raw evidence is published.

## Controlled empty-discovery run

The Device connection screen was opened with the glasses connected and no known compatible peripheral nearby.

Observed result:

```text
PERIPHERAL_SELECTED=NO
PERIPHERAL_PAIRED=NO
CAPTURE_STATUS=COMPLETE
```

No compatible device appeared.

The result is useful as a negative control, but by itself cannot identify the location of the scanner.

## Android-side scan attribution

The capture did not expose a Rokid-specific Android scan filter by device name, primary UUID, solicitation UUID, or manufacturer identifier.

Observed service-data filters:

```text
FE2C
FEAA
FFF6
```

These were unrelated background/platform scans and must not be used as an emulation target.

An earlier `0x9100` service filter was associated with the glasses themselves during Android Companion Device Manager association. It is not evidence of a ring UUID.

## Application resources

The packaged resources contain an explicit setting description for rings and control panels:

```text
prompter_settings_connect_device_desc
```

They also contain labels for Device connection, an accessory/peripheral, and an Ignore Peripheral action. This establishes deliberate product support for an external-controller workflow, but not the identity or protocol of a supported device.

## Native CXR boundary

`libcxr-bridge-jni.so` contains an exported weak symbol:

```text
NativeCXRBridge::startBTPairing(unsigned int)
```

The relevant function is version-specific and was found in the tested build at virtual address `0x14b68`, with a symbol-table size of 316 bytes.

Its behavior is approximately:

```cpp
void NativeCXRBridge::startBTPairing(uint32_t value) {
    rokid::Caps outer;
    rokid::Caps inner;

    outer.write(0u);
    inner.write("startBTPairing");
    inner.write(value);
    outer.write(inner);

    transport_virtual_call("CXRControl", outer);
}
```

`transport_virtual_call` is a descriptive placeholder. The vtable target was not symbolically identified.

The `CXRControl` string is reconstructed from the function's in-place libc++ short-string construction. The command string `startBTPairing` is loaded from read-only data and written into the nested Caps object.

## JNI boundary

`JNI_OnLoad` initializes both:

```text
CapsHelperInitialize
CXRBridgeInitialize
```

The protected application layer did not yield a readable Java/Kotlin call site in ordinary JADX output. The native command boundary nevertheless remains directly visible.

## Interpretation

The strongest supported interpretation is:

- the phone application requests pairing through the existing Rokid CXR control channel;
- the request is directed toward the connected glasses control plane;
- the glasses likely perform or manage discovery for accepted peripherals.

The analysis does not prove the behavior of the receiving glasses firmware. It also does not rule out some phone-side participation after the control response.

## Claims deliberately not made

This experiment does not claim:

- that the expected device is `RGR06`;
- that any short mixed-case `Rgr` string fragment is a model identifier;
- that `FE2C`, `FEAA`, `FFF6`, or `0x9100` describe the optional peripheral;
- that `WordTips_AllDevices` definitively means peripheral discovery;
- that advertising only a product name would satisfy the glasses;
- that the unsigned integer argument has a known semantic value.

## Outcome

The pairing-control boundary is sufficiently characterized for the current project. Identifying the downstream BLE protocol requires a compatible reference device, so the investigation is closed.
