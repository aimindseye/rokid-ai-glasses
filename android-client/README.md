# Rokid Channel Probe

A bounded Android research companion through `r1.3.3.2.25.2.4`.

## Current qualified capability

The repository contains a device-qualified **connection-only RFCOMM client**.
The accepted strict-handoff workflow:

1. receives a private runtime endpoint handoff from the host runner;
2. attests that the handoff is fresh and the probe is ready;
3. opens exactly one Android client-side RFCOMM socket;
4. uses the observed protocol invariants SCN `3`, DLCI `6`, and MTU `990`;
5. obtains no application input/output streams and sends no payload;
6. closes the socket and revokes the handoff;
7. correlates the Android lifecycle with a lossless HCI DLCI census.

The accepted result proves TX `0` application bytes and RX `0` application
bytes for the measured connection-only attempt. See the
[final publication](../docs/research/connection-protocol/r1.3.3.2.25.2.4-final-rfcomm-client-zero-payload-closure.md).

## Supporting probe modes

- BLE advertisement scan;
- bonded-device inventory;
- SDP UUID discovery for bonded devices;
- BLE GATT connection and service/characteristic inventory;
- reads only characteristics that advertise `PROPERTY_READ`;
- power-state differential BLE attribution;
- stock-assisted endpoint correlation using private per-run HMAC material;
- JSONL evidence written to app-private storage;
- device addresses pseudonymized or kept private according to the run contract.

## Deliberately absent

- Internet permission;
- arbitrary GATT or descriptor writes;
- application-payload RFCOMM reads or writes;
- user-supplied raw payload transmission;
- hidden APIs;
- account login or binding bypass;
- CXR message construction or replay;
- Developer Mode or USB ADB toggle.

This is a transport research client, not a complete replacement companion.

## Build

Open this directory in Android Studio, install Android SDK 36, and build the
`app` module. The project pins Android Gradle Plugin 8.13.0 and uses Java 17.
With the committed wrapper:

```bash
./gradlew clean :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Evidence and privacy

The app writes private evidence to app-private storage. Pull it only through the
strict host runners. Raw endpoint values, handoff material, logs, bugreports,
and HCI captures must not be published.

Public status and evidence identities are available in:

- [connection-protocol index](../docs/research/connection-protocol/README.md);
- [runtime status](../docs/research/connection-protocol/r1.3.3.2.25.2.4-runtime-status-summary.json);
- [evidence hashes](../docs/research/connection-protocol/r1.3.3.2.25.2.4-evidence-hashes.txt).

## Historical modes

### r25.2 connection-only bootstrap

The initial r25.2 flow read GATT service `0x9100`, characteristic `0x9301`,
acquired the runtime RFCOMM identity in memory, and implemented an intentionally
zero-payload connect/close path. Later strict-handoff and HCI phases supplied the
accepted hardware qualification.

### r25.2.1 power-state BLE attribution

This capture-only mode records bounded glasses-off, power-on-transition, and
steady-on BLE scan phases. It exposes no GATT or RFCOMM action.

### r25.2.2 stock-assisted correlation

This connection-free mode uses Hi Rokid as a bounded attribution oracle and a
private per-run HMAC key to correlate stock provisioning activity without
publishing a raw address.

### r25.2.3.2 strict-handoff HCI qualification

This mode reuses the accepted strict private-handoff runner, starts measurement
only after readiness, permits exactly one connection action, captures the
bugreport after close, and revokes the handoff. Its evidence is authoritative
for the final r25.2.4 publication.

## Next implementation boundary

The next phase must capture and decode the stock ADB-enable and ADB-disable
application payloads. Custom payload transmission remains disabled until framing,
authentication/integrity fields, reply correlation, and rollback are proven.
