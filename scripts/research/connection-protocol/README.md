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
