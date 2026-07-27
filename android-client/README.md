# Rokid Channel Probe

A bounded Android companion probe through r1.3.3.2.25.2.

## Capabilities

- BLE advertisement scan;
- bonded-device inventory;
- SDP UUID discovery for bonded devices;
- BLE GATT connection and service/characteristic inventory;
- reads only characteristics that advertise `PROPERTY_READ`;
- JSONL evidence written to app-private storage;
- device addresses pseudonymized with a per-run salt.

## Deliberately absent

- Internet permission;
- GATT or descriptor writes;
- RFCOMM socket connection;
- hidden APIs;
- account login or binding bypass;
- CXR message construction;
- Developer Mode or USB toggle.

## Build

Open this directory in Android Studio, install Android SDK 36, and build the `app` module.

The project pins Android Gradle Plugin 8.13.0 and uses Java 17. With Gradle 8.13 available:

```bash
gradle :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Evidence

The app displays the generated JSONL path. Pull it with `run-as`; do not publish the raw log until it has passed the r25 sanitizer.


## r25.2 connection-only qualification

The r25.2 flow adds one explicitly bounded operation:

1. read GATT service `0x9100`, characteristic `0x9301`;
2. acquire the runtime RFCOMM UUID and Classic address in memory;
3. log only hashes, lengths, and pseudonymous device identity;
4. open RFCOMM using the runtime UUID;
5. never obtain the socket input or output stream;
6. send and read zero application payload bytes;
7. close after approximately two seconds.

Run it only while Hi Rokid is disabled for the current Android user. The device must remain bonded. See `scripts/research/connection-protocol/run_r1_3_3_2_25_2.sh`.

Build with the committed wrapper:

```bash
./gradlew clean :app:assembleDebug
```

## r25.2.1 power-state BLE attribution mode

The r25.2.1 build temporarily replaces the connection-only UI with a
capture-only identity-attribution workflow. It records three bounded BLE scan
phases:

1. glasses powered off — 20 seconds;
2. immediate power-on transition — 30 seconds;
3. glasses powered on and steady — 30 seconds.

Each phase auto-stops. Duplicate scan starts are rejected before Android's
scanner is called. The private JSONL records pseudonymous device IDs, RSSI,
connectability, advertised UUIDs, manufacturer company IDs, lengths, and SHA-256
fingerprints of advertisement material. Raw Bluetooth addresses and raw payload
bytes are not written by the r25.2.1 attribution probe.

The r25.2.1 UI exposes no GATT or RFCOMM action. Run it with:

```bash
scripts/research/connection-protocol/run_r1_3_3_2_25_2_1.sh
```


## r1.3.3.2.25.2.2 stock-assisted correlation mode

The r25.2.2 build remains connection-free. It captures three bounded BLE scan phases and writes a private per-run HMAC key so the host can correlate a raw stock-app GATT address to scan observations without logging that address in the application JSONL. Hi Rokid is enabled only by the host runner during the 60-second stock-assist window.
