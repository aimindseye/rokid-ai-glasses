# Peripheral Pairing Control Path

## Finding

Hi Rokid contains a native operation that packages an external-peripheral pairing request as a Rokid Caps command and sends it to the `CXRControl` endpoint.

The command payload contains the literal operation name:

```text
startBTPairing
```

and one unsigned integer argument whose meaning is unknown.

## Evidence summary

The finding is supported by:

- a product UI explicitly describing rings and control panels;
- a completed empty-discovery run with no peripheral selected or paired;
- no observed phone-side Rokid-specific BLE scan filter;
- the exported native symbol `NativeCXRBridge::startBTPairing(unsigned int)`;
- disassembly showing nested `rokid::Caps` construction;
- reconstruction of the destination string `CXRControl`;
- absence of Android BLE/GATT scanning calls inside the native function.

## Confidence

| Statement | Confidence |
|---|---|
| The application deliberately supports an optional peripheral workflow | High |
| `startBTPairing` is a real outbound CXR control operation | High |
| The phone delegates pairing initiation to the connected glasses control plane | High |
| The glasses perform the BLE scan themselves | Moderate to high |
| `RGR06` is a supported device | Unknown |
| The peripheral advertisement or GATT protocol is known | No |

The distinction between the last two delegation statements matters: the native function proves a command is sent toward the glasses control plane, while the actual receiving implementation was not inspected.

## Architectural implication

For an independent Android companion application, there are two separate controller strategies:

1. **Application-owned controller path**
   Pair a standard BLE/HID controller directly with Android and map its events inside the custom companion application.

2. **Glasses-owned controller path**
   Reproduce Rokid's proprietary `CXRControl/startBTPairing` behavior and the expected glasses-side peripheral protocol.

The first strategy is practical without a compatible Rokid ring. The second cannot be implemented reliably from the current evidence because the expected advertisement, GATT profile, authentication, and event protocol remain unknown.

## Closed research boundary

The project will not purchase a compatible ring for reference analysis. The effort therefore ends at the confirmed phone-to-glasses pairing-command boundary.
