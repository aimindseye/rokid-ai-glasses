# Rokid Channel Probe

A deliberately read-only Android companion bootstrap for r1.3.3.2.25.

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
