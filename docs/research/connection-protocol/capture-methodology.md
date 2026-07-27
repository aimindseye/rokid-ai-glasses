# r25 Capture Methodology

The stock workflow and independent client are observed separately.

1. Capture phone logcat and Bluetooth-manager/service snapshots.
2. Mark exact operator-action windows.
3. Capture glasses-side ADB state when available.
4. Optionally collect a phone bugreport and extract Bluetooth HCI snoop privately.
5. Reduce HCI data to metadata: timestamps, ATT handles/opcodes, UUIDs, PSMs, RFCOMM channels, payload lengths and payload hashes.
6. Run the independent read-only client to inventory advertisements, bonded-device SDP UUIDs, GATT services and readable characteristics.
7. Correlate the two evidence streams without publishing addresses or raw payloads.

A temporal packet burst is not assigned command semantics without repeated controlled A/B evidence.
