# Stock Connection Protocol Scripts

These scripts support r1.3.3.2.25:

- `run_r1_3_3_2_25.sh` — end-to-end interactive stock capture and bounded analysis;
- `run_r25_stock_capture.py` — synchronized phase and ADB snapshot capture;
- `extract_bluetooth_snoop.py` — private HCI extraction;
- `extract_bluetooth_metadata.py` — payload-free protocol metadata;
- `analyze_client_probe.py` — read-only Android client JSONL analysis;
- `analyze_pairing_channel.py` — stock/client transport correlation;
- `analyze_developer_mode_attribution.py` — fail-closed state/transport classification;
- `generate_r25_publication.py` and `verify_sanitized_r25_publication.py` — public output;
- `finalize_r25.py` — private evidence manifest and ZIP.

The tooling never sends a proprietary command and never writes a Bluetooth characteristic.
<!-- BEGIN R1.3.3.2.25.1 SCRIPTS -->
## r25.1 additions

- `analyze_r25_1_stock_session.py` — extracts fixed/runtime UUID behavior, BLE bootstrap, SDP channel, L2CAP CIDs, RFCOMM SCN/DLCI/MTU and timing;
- `run_r1_3_3_2_25_1.py` — end-to-end private analysis, public verification, run validation and finalization;
- `verify_r25_1_publication.py` — rejects raw addresses, account material and runtime UUID publication;
- `validate_r25_1_run.py` — enforces the exact closure boundary.
<!-- END R1.3.3.2.25.1 SCRIPTS -->

## r25.2 scripts

- `run_r1_3_3_2_25_2.sh` — strict device runner and stock restoration.
- `analyze_r25_2_client.py` — event-sequence, privacy, and zero-I/O validator.
- `verify_r25_2_publication.py` — sanitized publication gate.
- `finalize_r25_2.py` — private evidence manifest and archive.

## r25.2.1 scripts

- `run_r1_3_3_2_25_2_1.sh` — strict-isolation three-phase device runner;
- `analyze_r25_2_1_power_state.py` — differential fingerprint clustering and fail-closed candidate gate;
- `verify_r25_2_1_publication.py` — public privacy and zero-connection-scope gate;
- `finalize_r25_2_1.py` — private manifest and evidence ZIP;
- `test_r25_2_1_synthetic.py` — deterministic unique-candidate synthetic test.


### r25.2.2 tools

- `run_r1_3_3_2_25_2_2.sh`: stock-disabled baseline, bounded stock assist, post-stock handoff, logcat/optional bugreport collection, analysis, verification, and finalization.
- `analyze_r25_2_2_stock_assist.py`: unique provisioning-GATT address attribution and scan-token correlation.
- `verify_r25_2_2_publication.py`: fails on raw address or key disclosure.
- `finalize_r25_2_2.py`: seals private evidence.
