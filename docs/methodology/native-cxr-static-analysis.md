# Native CXR Static-Analysis Method

This document describes the sanitized method used to attribute the Device connection feature. It does not include proprietary application files or raw device evidence.

## Resource attribution

Android `aapt2 dump resources` was used to resolve the visible UI text to:

```text
string/prompter_settings_connect_device_desc
```

The extracted resource described connecting Bluetooth rings or control panels for interaction with the glasses.

## Decompiled-source boundary

JADX recovered resource declarations and the application manifest, including the companion-device service registration, but did not recover readable implementation call sites for the pairing operation.

The application uses a NetEase loader/protection wrapper, so absence of a Java call site was treated as a tooling boundary rather than evidence that the feature was absent.

## Native symbol attribution

The arm64 native library was inspected with Homebrew LLVM tools:

```text
llvm-nm
llvm-readelf
llvm-objdump
```

The dynamic symbol table identified:

```text
NativeCXRBridge::startBTPairing(unsigned int)
```

Address-range disassembly was used after symbol-name-specific disassembly failed on the weak C++ symbol.

## Command reconstruction

The function:

1. creates two `rokid::Caps` objects;
2. writes `0` to the outer object;
3. writes the literal string `startBTPairing` to the inner object;
4. writes the function argument to the inner object;
5. nests the inner object in the outer object;
6. constructs the short string `CXRControl`;
7. passes the endpoint string and Caps envelope to a virtual transport method.

The virtual method's symbolic name was not recovered. No claim is made about its exact C++ signature beyond the observed register arguments.

## Interpretation controls

The analysis intentionally separates:

- directly observed strings and instructions;
- high-confidence reconstruction;
- inference about the receiving glasses firmware.

No attempt was made to invoke the native function outside the vendor application, modify the APK, bypass device security, or send synthetic pairing commands.
