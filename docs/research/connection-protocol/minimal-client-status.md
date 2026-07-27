# Minimal Android Companion Client Status

The first client is an offline, read-only protocol probe.

Implemented:

- BLE scan;
- bonded-device inventory;
- SDP UUID discovery;
- GATT connection and service inventory;
- reads of characteristics that advertise `PROPERTY_READ`;
- pseudonymous JSONL evidence.

Not implemented:

- account binding or cloud login;
- proprietary CXR authentication;
- RFCOMM connection;
- GATT writes;
- command replay;
- Developer Mode toggle.

This is the correct first bootstrap because it can confirm the visible transport boundary without risking state mutation.
