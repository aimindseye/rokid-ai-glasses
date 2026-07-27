#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from r25lib import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    private = read_json(args.summary)
    pairing = private["pairing_channel"]
    developer = private["developer_mode"]
    client = private["client_probe"]

    public = {
        "schema": "rokid.r25.public-status.v1",
        "pairing_channel": {
            "status": pairing.get("status"),
            "known_static_boundary": pairing.get("known_static_boundary"),
            "transport_counts": pairing.get("transport_counts", {}),
            "phase_transport_counts": pairing.get("phase_transport_counts", {}),
            "gatt_service_uuid_count": len(pairing.get("gatt_uuids", [])),
            "sdp_uuid_count": len(pairing.get("sdp_uuids", [])),
            "rfcomm_channel_count": len(pairing.get("rfcomm_channels", [])),
            "session_authentication_contract": pairing.get("session_authentication_contract"),
            "message_framing_contract": pairing.get("message_framing_contract"),
            "independent_stock_session_implemented": False,
        },
        "developer_mode": {
            "classification": developer.get("classification"),
            "state_transition_count": len(developer.get("state_transitions", [])),
            "candidate_message_count": len(developer.get("candidate_messages", [])),
            "remote_invocation_closed": developer.get("remote_invocation_closed", False),
            "known_setting_key": developer.get("known_setting_key"),
            "known_enable_effects": developer.get("known_enable_effects", []),
            "known_disable_effects": developer.get("known_disable_effects", []),
        },
        "minimal_client": {
            "event_count": client.get("event_count", 0),
            "gatt_service_count": len(client.get("gatt_service_uuids", [])),
            "sdp_uuid_count": len(client.get("sdp_uuids", [])),
            "write_events": client.get("write_events", 0),
            "stock_session_qualified": False,
            "developer_mode_write_enabled": False,
        },
        "acceptance": "PASS_BOUNDED_CAPTURE" if private.get("live_closure") else "PASS_BOOTSTRAP_READY",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "r25-public-status.json", public)

    md = f"""# r25 Stock Channel and Minimal Client Status

## Pairing channel

- Status: `{public['pairing_channel']['status']}`
- Known static control boundary: `CXRControl/startBTPairing`
- Independent stock session implemented: **No**
- Authentication and framing: **Unresolved**

## Developer Mode

- Known setting key: `settings_developer_mode`
- Attribution classification: `{public['developer_mode']['classification']}`
- State transitions observed: {public['developer_mode']['state_transition_count']}
- Remote invocation closed: **No**

## Minimal client

- Read-only GATT service count: {public['minimal_client']['gatt_service_count']}
- SDP UUID count: {public['minimal_client']['sdp_uuid_count']}
- Bluetooth write events: {public['minimal_client']['write_events']}
- Stock session qualified: **No**

This publication does not contain raw Bluetooth payloads, MAC addresses, serials, account data, tokens, or private logs.
"""
    (args.output / "README.md").write_text(md, encoding="utf-8")
    print("R1_3_3_2_25_PUBLICATION=GENERATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
